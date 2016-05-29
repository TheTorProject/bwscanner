from twisted.internet import defer, reactor
from twisted.internet.endpoints import TCP4ClientEndpoint
from twisted.trial import unittest
from txtorcon.torstate import TorState, build_tor_connection

from bwscanner.attacher import SOCKSClientStreamAttacher, start_tor

import os
import random

class TorTestCase(unittest.TestCase):
    """
    XXX: Use code from circuit.py for the path selection rather than
         repeating path selection here.
    """

    @defer.inlineCallbacks
    def setUp(self):
        self.tor = yield build_tor_connection(
            TCP4ClientEndpoint(reactor, 'localhost', int(
                os.environ.get('CHUTNEY_CONTROL_PORT'))))

        self.attacher = SOCKSClientStreamAttacher(self.tor)
        yield self.tor.set_attacher(self.attacher, reactor)

    @property
    def routers(self):
        return list(set(self.tor.routers.values()))

    @property
    def exits(self):
        return [r for r in self.routers if 'exit' in r.flags]

    def random_path(self):
        exit_relay = random.choice(self.exits)
        selected_relays = random.sample(self.routers, 3)
        if exit_relay in selected_relays:
            selected_relays.remove(exit_relay)
        return selected_relays[0:2] + [exit_relay]

    @defer.inlineCallbacks
    def tearDown(self):
        yield self.tor.set_attacher(None, reactor)
        yield self.tor.protocol.quit()
        # seems to leave dirty reactor otherwise?
        yield self.tor.protocol.transport.loseConnection()
