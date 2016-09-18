import os
import sys
import time

import click
from twisted.internet import reactor
from txtorcon import build_local_tor_connection, TorConfig

from bwscanner.logger import setup_logging, log
from bwscanner.attacher import start_tor, update_tor_config, FETCH_ALL_DESCRIPTOR_OPTIONS
from bwscanner.measurement import BwScan


BWSCAN_VERSION = '0.0.1'


def connect_to_tor(launch_tor, circuit_build_timeout, circuit_idle_timeout):
    """
    Launch or connect to a Tor instance

    Configure Tor with the passed options and return a Deferred
    """
    # Options for spawned or running Tor to load the correct descriptors.
    tor_options = {
        'LearnCircuitBuildTimeout': 0,  # Disable adaptive circuit timeouts.
        'CircuitBuildTimeout': circuit_build_timeout,
        'CircuitIdleTimeout': circuit_idle_timeout,
    }

    def tor_status(tor):
        log.info("Connected successfully to Tor.")
        return tor

    if launch_tor:
        log.info("Spawning a new Tor instance.")
        c = TorConfig()
        # Update Tor config before launching a new Tor.
        c.config.update(tor_options)
        c.config.update(FETCH_ALL_DESCRIPTOR_OPTIONS)
        tor = start_tor(c)

    else:
        log.info("Trying to connect to a running Tor instance.")
        tor = build_local_tor_connection(reactor)
        # Update the Tor config on a running Tor.
        tor.addCallback(update_tor_config, tor_options)
        tor.addCallback(update_tor_config, FETCH_ALL_DESCRIPTOR_OPTIONS)

    tor.addCallback(tor_status)
    return tor


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
@click.option('--circuit-idle-timeout', default=20,
              help='Option passed when launching Tor.')
@click.version_option(BWSCAN_VERSION)
@click.pass_context
def cli(ctx, data_dir, loglevel, logfile, launch_tor, circuit_build_timeout, circuit_idle_timeout):
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
    ctx.obj.tor = connect_to_tor(launch_tor, circuit_build_timeout, circuit_idle_timeout)

    # Set up the logger to only output log lines of level `loglevel` and above.
    setup_logging(log_level=loglevel, log_name=logfile)


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
    scan_data_dir = os.path.join(scan.measurement_dir, '{}.running'.format(scan_time))
    if not os.path.isdir(scan_data_dir):
        os.makedirs(scan_data_dir)

    def rename_finished_scan(deferred):
        click.echo(deferred)
        os.rename(scan_data_dir, os.path.join(scan.measurement_dir, scan_time))

    scan.tor.addCallback(BwScan, reactor, scan_data_dir, request_timeout=timeout,
                         request_limit=request_limit, partitions=partitions,
                         this_partition=current_partition)
    scan.tor.addCallback(lambda scanner: scanner.run_scan())
    scan.tor.addCallback(lambda _: reactor.stop())
    scan.tor.addCallback(rename_finished_scan)

    reactor.run()


@cli.command(short_help="Combine bandwidth measurements.")
def aggregate():
    """
    Command to aggregate BW measurements to create file for the BWAuths
    """
    log.info("Aggregating bandwidth measurements.")
    log.warn("Not implemented yet!")
