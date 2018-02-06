import os
import sys
import time

import click
from twisted.internet import reactor

from bwscanner.attacher import connect_to_tor
from bwscanner.logger import setup_logging, log
from bwscanner.measurement import BwScan
from bwscanner.aggregate import write_aggregate_data


BWSCAN_VERSION = '0.0.1'
BASEURL = 'https://siv.sunet.se/bwauth/'
BWFILES = {
    64 * 1024: ("64M", "6258de4f4d602be75a3458117b29d2c580c4bcb7ba5b9d2c4135c7603109f554"),
    32 * 1024: ("32M", "5a5d66d7865f09498d776f20c9e9791b055a4fff357185f84fb4ecfca7da93f0"),
    16 * 1024: ("16M", "6258de4f4d602be75a3458117b29d2c580c4bcb7ba5b9d2c4135c7603109f554"),
    8 * 1024: ("8M", "738c5604295b9377f7636ce0c2c116f093bb50372f589a6c2332a3bb6bba096a"),
    4 * 1024: ("4M", "4daaa42377d3c87577797d44a8fa569038e7a9d6a5d417a09d8ba41a69456164"),
    2 * 1024: ("2M", "3e39b0bb92912cf1ad6c01fb7c9d592e814a691c61de1f649416f6bba2d15082"),

    # TODO: check whether files smaller than 2M should be provided
    # TODO: are k size files key correct?
    # 1024: ("1M", "daf6da82bc4a20567dcd5eb7e583f3137800c31eb31f5fed79f27a4278903780"),
    # 512: ("512k", "20e1e9b44c3cb445a59138df8a03767356637ec751beee1f9233ca881121adc6"),
    # 256: ("256k", "f3655613066fd0db916b0b00bde1a3905516584ea2c4ee4cac3a8ffb08f2f31c"),
    # 128: ("128k", "072b052df2fba25a9578b69d49986024747ad9e43472db345a03ca6e22027ba6"),
    # 64: ("64k", "73bee20c527362b18d4adb7e638a6513504954367379e7c61f7f45bdc71c5ddb"),
    # 32: ("32k", "2ec95ff2c8beca72996161e2bd7831008baf2e012d12b6c84d51e9264fc50fdc"),
    # 16: ("16k", "924bddcc93f8f76effd495c47b0d39451e34d8204029fe2b7f85905522255e7b"),
}


def validate_bwfiles(ctx, param, value):
    bwfiles = dict([(b * 1024, (str(b) + 'M',)) for b in value])
    return bwfiles


class ScanInstance(object):
    """
    Store the configuration and state for the CLI tool.
    """
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.measurement_dir = os.path.join(data_dir, 'measurements')

    def __repr__(self):
        return '<BWScan %r>' % self.data_dir


pass_scan = click.make_pass_decorator(ScanInstance)


@click.group()
@click.option('--data-dir', type=click.Path(),
              default=os.environ.get("BWSCANNER_DATADIR", click.get_app_dir('bwscanner')),
              help='Directory where bwscan should stores its measurements and '
              'other data.')
@click.option('-l', '--loglevel', help='The logging level the scanner will use (default: info)',
              default='info', type=click.Choice(['debug', 'info', 'warn', 'error', 'critical']))
@click.option('-f', '--logfile', type=click.Path(), help='The file the log will be written to',
              default=os.environ.get("BWSCANNER_LOGFILE", 'bwscanner.log'))
@click.option('--launch-tor/--no-launch-tor', default=False,
              help='Launch Tor or try to connect to an existing Tor instance.')
@click.option('--circuit-build-timeout', default=20,
              help='Option passed when launching Tor.')
@click.version_option(BWSCAN_VERSION)
@click.pass_context
def cli(ctx, data_dir, loglevel, logfile, launch_tor, circuit_build_timeout):
    """
    The bwscan tool measures Tor relays and calculates their bandwidth. These
    bandwidth measurements can then be aggregate to create the bandwidth
    values used by the Tor bandwidth authorities when creating the Tor consensus.
    """
    # Create the data directory if it doesn't exist
    data_dir = os.path.abspath(data_dir)
    ctx.obj = ScanInstance(data_dir)

    if not os.path.isdir(ctx.obj.measurement_dir):
        os.makedirs(ctx.obj.measurement_dir)

    # Create a connection to a Tor instance
    ctx.obj.tor_state = connect_to_tor(launch_tor, circuit_build_timeout)

    # Set up the logger to only output log lines of level `loglevel` and above.
    setup_logging(log_level=loglevel, log_name=logfile)


@cli.command(short_help="Measure the Tor relays.")
# FIXME: when having a configuration file the default will be given by it.
@click.option('--baseurl',
              help='URL that provides the files to perform the measurements with',
              default=BASEURL)
@click.option('--bwfiles', '-b',
              help='File size (in MB) to download from the baseurl server.'
              ' Several files can be provided by repeating this option.'
              'Example: -b 2 -b 4 ',
              callback=validate_bwfiles, multiple=True, default=BWFILES)
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
def scan(scan, baseurl, bwfiles, partitions, current_partition, timeout, request_limit):
    """
    Start a scan through each Tor relay to measure it's bandwidth.
    """
    log.info("Using {data_dir} as the data directory.", data_dir=scan.data_dir)

    # XXX: check that each run is producing the same input set!
    scan_time = str(int(time.time()))
    scan_data_dir = os.path.join(scan.measurement_dir, '{}.running'.format(scan_time))
    if not os.path.isdir(scan_data_dir):
        os.makedirs(scan_data_dir)

    def rename_finished_scan(deferred):
        click.echo(deferred)
        os.rename(scan_data_dir, os.path.join(scan.measurement_dir, scan_time))

    scan.tor_state.addCallback(BwScan, reactor, scan_data_dir, baseurl,
                               bwfiles,
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
