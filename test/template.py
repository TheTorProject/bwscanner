from twisted.internet import defer, reactor
from twisted.internet.endpoints import TCP4ClientEndpoint
from twisted.trial import unittest
from txtorcon.torstate import TorState, build_tor_connection

from bwscanner.attacher import SOCKSClientStreamAttacher, start_tor

import os
import random

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
        return [r for r in self.routers if 'exit' in r.flags]

    def random_path(self):
        return [random.choice(self.routers),
                random.choice(self.routers),
                random.choice(self.exits)]

    @defer.inlineCallbacks
    def tearDown(self):
        yield self.tor.set_attacher(None, reactor)
        yield self.tor.protocol.quit()
        # seems to leave dirty reactor otherwsie?
        yield self.tor.protocol.transport.loseConnection()
