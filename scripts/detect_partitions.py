#!/usr/bin/env python
"""
Two-Hop Relay Connectivity Tester

A scanner to probe all possible two hop circuits to detect network
partitions where some relays are not able to connect to other relays.
"""

import click
import sys
import hashlib
import signal

from twisted.python import log
from twisted.internet import reactor
from twisted.internet.endpoints import clientFromString

import txtorcon
from txtorcon import TorState

from bwscanner.partition_scan import ProbeAll2HopCircuits


@click.command()
@click.option('--tor-control', default=None, type=str, help="tor control port as twisted endpoint descriptor string")
@click.option('--tor-data', default=None, type=str, help="launch tor data directory")
@click.option('--log-dir', default="./logs", type=str, help="log directory")
@click.option('--relays-file', default=None, type=str, help="file containing serialized list of tor router objects")
@click.option('--secret', default=None, type=str, help="secret")
@click.option('--partitions', default=None, type=int, help="total number of permuation partitions")
@click.option('--this-partition', default=None, type=int, help="which partition to scan")
@click.option('--build-duration', default=0.2, type=float, help="circuit build duration")
@click.option('--circuit-timeout', default=10.0, type=float, help="circuit build timeout")
@click.option('--prometheus-port', default=None, type=int, help="prometheus port to listen on")
@click.option('--prometheus-interface', default=None, type=str, help="prometheus interface to listen on")
def main(tor_control, tor_data, log_dir, relays_file,
         secret, partitions, this_partition, build_duration, circuit_timeout, prometheus_port, prometheus_interface):

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
        d = txtorcon.build_tor_connection(endpoint, build_state=True)

    with open(relays_file, "r") as rf:
        relay_lines = rf.read()
    relays = []

    secret_hash = hashlib.sha256(secret).digest()
    def start_probe(tor_state):
        for relay_line in relay_lines.split():
            relay = tor_state.router_from_id(relay_line)
            relays.append(relay)
        print "end of relay serialization"
        probe = ProbeAll2HopCircuits(tor_state, reactor, log_dir, reactor.stop, relays, secret_hash,
                                     partitions, this_partition, build_duration, circuit_timeout, prometheus_port, prometheus_interface)
        print "starting scan"
        probe.start()
        def signal_handler(signal, frame):
            print "signal caught, stopping probe"
            d = probe.stop()
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    d.addCallback(start_probe)
    reactor.run()

if __name__ == '__main__':
    main()
