import os
import sys

import click
from twisted.internet import reactor
from twisted.python import log
from txtorcon import build_local_tor_connection, TorConfig

from bwscanner.attacher import start_tor, update_tor_config, FETCH_ALL_DESCRIPTOR_OPTIONS
from bwscanner.measurement import BwScan


BWSCAN_VERSION = '0.0.1'


class ScanInstance(object):
    """
    Store the configuration and state for the CLI tool.
    """
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.verbose = False

    def __repr__(self):
        return '<BWScan %r>' % self.data_dir

pass_scan = click.make_pass_decorator(ScanInstance)


@click.group()
@click.option('--verbose/--no-verbose', default=False,
              help='Enables verbose mode.')
@click.option('--data-dir', type=click.Path(),
              default=os.environ.get("BWSCANNER_DATADIR", click.get_app_dir('bwscanner')),
              help='Directory where bwscan should stores its measurements and '
              'other data.')
@click.version_option(BWSCAN_VERSION)
@click.pass_context
def cli(ctx, verbose, data_dir):
    """
    The bwscan tool measures Tor relays and calculates their bandwidth. These
    bandwidth measurements can then be aggregate to create the bandwidth
    values used by the Tor bandwidth authorities when creating the Tor consensus.
    """
    # Create the data directory if it doesn't exist
    data_dir = os.path.abspath(data_dir)
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    ctx.obj = ScanInstance(data_dir)
    ctx.obj.verbose = verbose


@cli.command(short_help="Measure the Tor relays.")
@click.option('--partitions', '-p', default=1,
              help='Divide the set of relays into subsets. 1 by default.')
@click.option('--current-partition', '-c', default=1,
              help='Scan a particular subset / partition of the relays.')
@click.option('--timeout', default=120,
              help='Timeout for measurement HTTP requests (default: %ds).' % 120)
@click.option('--launch-tor/--no-launch-tor', default=True,
              help='Launch Tor or try to connect to an existing Tor instance.')
@click.option('--circuit-build-timeout', default=20,
              help='Option passed when launching Tor.')
@click.option('--circuit-idle-timeout', default=20,
              help='Option passed when launching Tor.')
@pass_scan
def scan(scan, launch_tor, partitions, current_partition, timeout,
         circuit_build_timeout, circuit_idle_timeout):
    """
    Start a scan through each Tor relay to measure it's bandwidth.
    """
    if scan.verbose:
        log.startLogging(sys.stdout)
        click.echo('Verbose log mode is on.')
        click.echo('Using %s as the data directory.' % scan.data_dir)

    # Options for spawned or running Tor to load the correct descriptors.
    tor_options = {
        'LearnCircuitBuildTimeout': 0,  # Disable adaptive circuit timeouts.
        'CircuitBuildTimeout': circuit_build_timeout,
        'CircuitIdleTimeout': circuit_idle_timeout,
    }

    def tor_status(tor):
        click.echo("Connected to a Tor instance.")
        return tor

    if launch_tor:
        click.echo("Spawning a new Tor instance")
        c = TorConfig()
        # Update Tor config before launching a new Tor.
        c.config.update(tor_options)
        c.config.update(FETCH_ALL_DESCRIPTOR_OPTIONS)
        tor = start_tor(c)

    else:
        click.echo("Connecting to a running Tor instance")
        tor = build_local_tor_connection(reactor)
        # Update the Tor config on a running Tor.
        tor.addCallback(update_tor_config, tor_options)
        tor.addCallback(update_tor_config, FETCH_ALL_DESCRIPTOR_OPTIONS)

    tor.addCallback(tor_status)

    # XXX: check that each run is producing the same input set!
    measurement_dir = os.path.join(scan.data_dir, 'measurements')
    if not os.path.exists(measurement_dir):
        os.makedirs(measurement_dir)

    tor.addCallback(BwScan, reactor, measurement_dir, request_timeout=timeout,
                    partitions=partitions, this_partition=current_partition)
    tor.addCallback(lambda scanner: scanner.run_scan())
    tor.addCallback(lambda _: reactor.stop())
    reactor.run()


@cli.command(short_help="Combine bandwidth measurements.")
def aggregate():
    """
    Command to aggregate BW measurements to create file for the BWAuths
    """
    click.echo('Aggregating bandwidth measurements')
    click.echo('Not implemented yet')
