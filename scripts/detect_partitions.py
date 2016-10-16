#!/usr/bin/env python
"""
Two-Hop Relay Connectivity Tester

A scanner to probe all possible two hop circuits to detect network
partitions where some relays are not able to connect to other relays.
"""

import click
import sys

from twisted.python import log
from twisted.internet import reactor
from twisted.internet.endpoints import clientFromString

import txtorcon
from txtorcon import TorState

from bwscanner.partition_scan import ProbeAll2HopCircuits


@click.command()
@click.option('--tor-control', default=None, type=str, help="tor control port as twisted endpoint descriptor string")
@click.option('--tor-data', default=None, type=str, help="launch tor data directory")
@click.option('--relays-file', default=None, type=str, help="file containing serialized list of tor router objects")
@click.option('--secret', default=None, type=str, help="secret")
@click.option('--partitions', default=None, type=int, help="total number of permuation partitions")
@click.option('--this-partition', default=None, type=int, help="which partition to scan")
@click.option('--build-duration', default=0.2, type=float, help="circuit build duration")
@click.option('--circuit-timeout', default=10.0, type=float, help="circuit build timeout")
def main(tor_control, tor_data, relays_file, secret, partitions, this_partition, build_duration, circuit_timeout):
    log.startLogging( sys.stdout )
    def start_tor():
        config = txtorcon.TorConfig()
        config.DataDirectory = tor_data

        def get_random_tor_ports():
            d2 = txtorcon.util.available_tcp_port(reactor)
            d2.addCallback(lambda port: config.__setattr__('SocksPort', port))
            d2.addCallback(lambda _: txtorcon.util.available_tcp_port(reactor))
            d2.addCallback(lambda port: config.__setattr__('ControlPort', port))
            return d2

        def launch_and_get_protocol(ignore):
            d2 = txtorcon.launch_tor(config, reactor, stdout=sys.stdout)
            d2.addCallback(lambda tpp: txtorcon.TorState(tpp.tor_protocol).post_bootstrap)
            d2.addCallback(lambda state: state.protocol)
            return d2

        d = get_random_tor_ports().addCallback(launch_and_get_protocol)
        def change_torrc(result):
            config.UseEntryGuards=0
            d2 = config.save()
            d2.addCallback(lambda ign: result)
            return d2
        d.addCallback(change_torrc)
        d.addCallback(lambda protocol: TorState.from_protocol(protocol))
        return d

    if tor_control is None:
        print "launching tor..."
        d = start_tor()
    else:
        print "using tor control port..."
        endpoint = clientFromString(reactor, tor_control.encode('utf-8'))
        d = txtorcon.build_tor_connection(endpoint, build_state=False)

    with open(relays_file, "r") as rf:
        relay_lines = rf.read()
    relays = []

    secret_hash = hashlib.sha256(secret).digest()
    def start_probe(tor_state):
        for relay_line in relay_lines:
            relay = tor_state.router_from_id(relay_line.rstrip())
            relays.append(relay)
        probe = ProbeAll2HopCircuits(tor_state, reactor, './logs', reactor.stop, relays, secret_hash,
                                     partitions, this_partition, build_duration, circuit_timeout)
        probe.start()
    d.addCallback(start_probe)
    reactor.run()

if __name__ == '__main__':
    main()
