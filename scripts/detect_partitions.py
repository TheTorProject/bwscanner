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
from stem.descriptor import parse_file, DocumentHandler

from twisted.python import log
from twisted.internet import reactor
from twisted.internet.endpoints import clientFromString

import txtorcon
from txtorcon import TorState

from bwscanner.partition_scan import ProbeAll2HopCircuits

def get_router_list_from_consensus(tor_state, consensus):
    """
    arguments
        tor_state is a txtorcon TorState object
        consensus_file is a file containing a tor network-status-consensus-3 document
    returns
        a list of routers (txtorcon Router router object)
    """
    routers = []
    with open(consensus, 'rb') as consensus_file:
        for relay in parse_file(consensus_file):
            if relay is not None and relay.fingerprint is not None:
                router = tor_state.router_from_id("$" + relay.fingerprint)
                routers.append(router)
            if len(routers) == 0:
                print "failed to parse consensus file"
                sys.exit(1)
    return routers

def get_router_list_from_file(tor_state, relay_list_file):
    """
    arguments
        tor_state is a txtorcon TorState object
        relay_list_file is a file containing one Tor relay fingerprint per line
    returns
        a list of routers (txtorcon Router router object)
    """
    routers = []
    with open(relays_list_file, "r") as rf:
        relay_lines = rf.read()
    for relay_line in relay_lines.split():
        router = tor_state.router_from_id("$" + relay_line)
        routers.append(router)
    return routers


@click.command()
@click.option('--tor-control', default=None, type=str, help="tor control port as twisted endpoint descriptor string")
@click.option('--tor-data', default=None, type=str, help="launch tor data directory")
@click.option('--log-dir', default="./logs", type=str, help="log directory")
@click.option('--relay-list', default=None, type=str, help="file containing list of tor relay fingerprints, one per line")
@click.option('--consensus', default=None, type=str, help="file containing tor consensus document, network-status-consensus-3 1.0")
@click.option('--secret', default=None, type=str, help="secret")
@click.option('--partitions', default=None, type=int, help="total number of permuation partitions")
@click.option('--this-partition', default=None, type=int, help="which partition to scan")
@click.option('--build-duration', default=0.2, type=float, help="circuit build duration")
@click.option('--circuit-timeout', default=10.0, type=float, help="circuit build timeout")
@click.option('--prometheus-port', default=None, type=int, help="prometheus port to listen on")
@click.option('--prometheus-interface', default=None, type=str, help="prometheus interface to listen on")
def main(tor_control, tor_data, log_dir, relay_list, consensus,
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

    secret_hash = hashlib.sha256(secret).digest()
    def start_probe(tor_state):
        if consensus is not None:
            routers = get_router_list_from_consensus(tor_state, consensus)
        elif relay_list is not None:
            routers = get_router_list_from_file(tor_state, relay_list)
        else:
            pass  # XXX todo: print usage

        probe = ProbeAll2HopCircuits(tor_state, reactor, log_dir, reactor.stop, routers, secret_hash,
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
