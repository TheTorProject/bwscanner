#!/usr/bin/env python
"""
Two-Hop Relay Connectivity Tester

A scanner to probe all possible two hop circuits to detect network
partitioning problems where some relays are not able to connect to other
relays.
"""

import click
import sys

from twisted.python import log
from twisted.internet import reactor
from twisted.internet.endpoint import clientFromString

import txtorcon
from txtorcon import TorState

from bwscanner import ProbeAll2HopCircuits


@click.command()
@click.option('--tor-control', default=None, type=str, help="tor control port as twisted endpoint descriptor string")
@click.option('--tor-data', default=None, type=str, help="launch tor data directory")
def main(tor_control, tor_data):
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

    d.addCallback( ProbeAll2HopCircuits, reactor, './logs', stopped=reactor.stop )
    reactor.run()

if __name__ == '__main__':
    main()
