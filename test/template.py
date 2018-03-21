import os
import random

from twisted.internet import defer, reactor
from twisted.trial import unittest

from bwscanner import circuit
from bwscanner.attacher import SOCKSClientStreamAttacher, connect_to_tor


class TorTestCase(unittest.TestCase):

    @defer.inlineCallbacks
    def setUp(self):
        self.tor_state = yield connect_to_tor(
                launch_tor=False,
                control_port=int(os.environ.get('CHUTNEY_CONTROL_PORT')),
                circuit_build_timeout=30,
        )

        self.attacher = SOCKSClientStreamAttacher(self.tor_state)
        yield self.tor_state.set_attacher(self.attacher, reactor)

    @property
    def routers(self):
        # NOTE: circuit relays attributes is obtained this way
        return list(set(r for r in self.tor_state.routers.values() if r))

    @property
    def exits(self):
        return [r for r in self.routers if circuit.is_valid_exit(r)]

    def random_path(self):
        exit_relay = random.choice(self.exits)
        return circuit.random_path_to_exit(exit_relay, self.routers)

    @defer.inlineCallbacks
    def tearDown(self):
        yield self.tor_state.set_attacher(None, reactor)
        yield self.tor_state.protocol.quit()
        # seems to leave dirty reactor otherwise?
        yield self.tor_state.protocol.transport.loseConnection()
        
