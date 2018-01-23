import os
import random

from twisted.internet import defer, reactor
from twisted.internet.endpoints import TCP4ClientEndpoint
from twisted.trial import unittest
from txtorcon.torstate import build_tor_connection

from bwscanner import circuit
from bwscanner.attacher import SOCKSClientStreamAttacher


class TorTestCase(unittest.TestCase):

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
        return [r for r in self.routers if circuit.is_valid_exit(r)]

    def random_path(self):
        exit_relay = random.choice(self.exits)
        return circuit.random_path_to_exit(exit_relay, self.routers)

    @defer.inlineCallbacks
    def tearDown(self):
        yield self.tor.set_attacher(None, reactor)
        yield self.tor.protocol.quit()
        # seems to leave dirty reactor otherwise?
        yield self.tor.protocol.transport.loseConnection()
