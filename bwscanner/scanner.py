import os
import sys
import time

import click
from twisted.internet import reactor

from bwscanner.attacher import connect_to_tor
from bwscanner.configutil import read_config
from bwscanner.logger import setup_logging, log
from bwscanner.measurement import BwScan
from bwscanner.aggregate import write_aggregate_data


BWSCAN_VERSION = '0.0.1'
APP_NAME = 'bwscanner'
DATA_DIR = os.environ.get("BWSCANNER_DATADIR", click.get_app_dir(APP_NAME))
CONFIG_FILE = 'config.ini'
LOG_FILE = 'bwscanner.log'


class ScanInstance(object):
    """
    Store the configuration and state for the CLI tool.
    """
    def __init__(self, data_dir, measurement_dir=None):
        self.data_dir = data_dir
        if measurement_dir is None:
            self.measurement_dir = os.path.join(data_dir, 'measurements')
        else:
            self.measurement_dir = measurement_dir
        self.tor_state = None

    def __repr__(self):
        return '<BWScan %r>' % self.data_dir


pass_scan = click.make_pass_decorator(ScanInstance)


# FIXME: check these errors
# pylint: disable=unexpected-keyword-arg
# pylint: disable=no-value-for-parameter
@click.group()
@click.option('--data-dir', type=click.Path(),
              help='Directory where bwscan should stores its measurements and '
              'other data.')
@click.option('-l', '--loglevel',
              help='The logging level the scanner will use (default: info)',
              type=click.Choice(
                      ['debug', 'info', 'warn', 'error', 'critical']))
@click.option('-f', '--logfile', type=click.Path(),
              help='The file the log will be written to')
@click.option('--launch-tor/--no-launch-tor',
              help='Launch Tor or try to connect to an existing Tor instance.')
@click.option('--circuit-build-timeout',
              help='Option passed when launching Tor.')
@click.version_option(BWSCAN_VERSION)
@click.pass_context
def cli(ctx, data_dir, loglevel, logfile, launch_tor, circuit_build_timeout):
    """
    The bwscan tool measures Tor relays and calculates their bandwidth. These
    bandwidth measurements can then be aggregate to create the bandwidth
    values used by the Tor bandwidth authorities when creating the Tor consensus.
    """
    for k, v in ctx.default_map.items():
        if ctx.params.get(k) is None:
            ctx.params[k] = v

    # Create the data directory if it doesn't exist
    ctx.obj = ScanInstance(ctx.params.get('data_dir'))

    if not os.path.isdir(ctx.obj.measurement_dir):
        os.makedirs(ctx.obj.measurement_dir)

    # Create a connection to a Tor instance
    ctx.obj.tor_state = connect_to_tor(launch_tor, circuit_build_timeout,
                                       ctx.obj.tor_dir)

    # Set up the logger to only output log lines of level `loglevel` and above.
    setup_logging(log_level=ctx.params.get('loglevel'),
                  log_name=ctx.params.get('logfile'))


@cli.command(short_help="Measure the Tor relays.")
@click.option('--partitions', '-p', default=1,
              help='Divide the set of relays into subsets. 1 by default.')
@click.option('--current-partition', '-c', default=1,
              help='Scan a particular subset / partition of the relays.')
@click.option('--timeout', default=120,
              help='Timeout for measurement HTTP requests (default: %ds).' % 120)
@click.option('--request-limit', default=10,
              help='Limit the number of simultaneous bandwidth measurements '
              '(default: %d).' % 10)
@pass_scan
def scan(scan, partitions, current_partition, timeout, request_limit):
    """
    Start a scan through each Tor relay to measure it's bandwidth.
    """
    log.info("Using {data_dir} as the data directory.", data_dir=scan.data_dir)

    # XXX: check that each run is producing the same input set!
    scan_time = str(int(time.time()))
    scan_data_dir = os.path.join(scan.measurement_dir,
                                 '{}.running'.format(scan_time))
    if not os.path.isdir(scan_data_dir):
        os.makedirs(scan_data_dir)

    def rename_finished_scan(deferred):
        click.echo(deferred)
        os.rename(scan_data_dir, os.path.join(scan.measurement_dir, scan_time))

    scan.tor_state.addCallback(BwScan, reactor, scan_data_dir,
                               request_timeout=timeout,
                               request_limit=request_limit,
                               partitions=partitions,
                               this_partition=current_partition)
    scan.tor_state.addCallback(lambda scanner: scanner.run_scan())
    scan.tor_state.addCallback(lambda _: reactor.stop())
    scan.tor_state.addCallback(rename_finished_scan)

    reactor.run()


def get_recent_scans(measurement_dir):
    return sorted([name for name in os.listdir(measurement_dir) if name.isdigit()],
                  reverse=True)


@cli.command(short_help="List available bandwidth measurement directories.")
@pass_scan
def list(scan):
    """
    List the names of all completed scan directories
    """
    scan_data_dirs = get_recent_scans(scan.measurement_dir)
    if scan_data_dirs:
        for scan_dir in scan_data_dirs:
            click.echo(click.format_filename(scan_dir))
    else:
        log.warn("No completed scan data found in {measurement_dir}",
                 measurement_dir=scan.measurement_dir)


@cli.command(short_help="Combine bandwidth measurements.")
@click.option('-p', '--previous', type=int, default=1,
              help='The number of recent scans to include when aggregating.')
@click.argument('scan_name', required=False)
@pass_scan
def aggregate(scan, scan_name, previous):
    """
    Command to aggregate BW measurements and create the bandwidth file for the BWAuths
    """
    # Aggregate the specified scan
    if scan_name:
        # Confirm that the specified scan directory exists
        scan_dir_path = os.path.join(scan.measurement_dir, scan_name)
        if not os.path.isdir(scan_dir_path):
            log.warn("Could not find scan data directory {scan_dir}.", scan_dir=scan_dir_path)
            sys.exit(-1)
        scan_data_dirs = [scan_dir_path]
        log.info("Aggregating bandwidth measurements for scan {scan_name}.", scan_name=scan_name)

    else:
        # Aggregate the n previous scan runs
        try:
            # Use the most recent completed scan by default
            recent_scan_names = get_recent_scans(scan.measurement_dir)[:previous]
        except IndexError:
            log.warn("Could not find any completed scan data.")
            sys.exit(-1)

        scan_data_dirs = [os.path.join(scan.measurement_dir, name) for name in recent_scan_names]
        log.info("Aggregating data from past {count} scans.", count=len(scan_data_dirs))

    scan.tor_state.addCallback(lambda tor_state: write_aggregate_data(tor_state, scan_data_dirs))
    scan.tor_state.addErrback(lambda failure: log.failure("Unexpected error"))
    scan.tor_state.addCallback(lambda _: reactor.stop())
    reactor.run()


def start():
    config = read_config(os.path.join(DATA_DIR, CONFIG_FILE))
    return cli(default_map=config)
