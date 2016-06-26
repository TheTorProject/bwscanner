import random

from twisted.internet import defer, reactor
from txtorcon.circuit import Circuit
from txtorcon.stream import Stream

#  from bwscanner.attacher import start_tor
from test.template import TorTestCase

# class TestLaunchTor(unittest.TestCase):
#     @defer.inlineCallbacks
#     def test_launch_tor(self):
#         """
#         Test start_tor helper method that picks random TCP ports for
#         the SOCKSPort and ControlPort.
#         """
#         self.tor = yield start_tor(TorConfig())
#         self.assertIsInstance(self.tor, TorState)

#     @defer.inlineCallbacks
#     def tearDown(self):
#         yield self.tor.protocol.quit()
#         # XXX: need to delay until tor has really exited. See:
#         # https://github.com/meejah/txtorcon/issues/172


class FakeCircuit(Circuit):
    def __init__(self, id=None):
        self.streams = []
        self.id = id or random.randint(2222, 7777)
        self.state = 'BOGUS'


class FakeStream(Stream):
    def __init__(self, id=-999, target_port=9999, target_host='127.0.0.1',
                 source_addr='127.0.0.1', source_port=9999):
        self.streams = []
        self.listeners = []
        self.id = id
        self.state = 'BOGUS'
        self.target_addr = ''
        self.target_host = target_host
        self.target_port = target_port
        self.source_addr = source_addr
        self.source_port = source_port
        self.circuit = None

    def listen(self, _):
        pass


class TestSOCKSClientStreamAttacher(TorTestCase):
    @defer.inlineCallbacks
    def setUp(self):
        yield super(TestSOCKSClientStreamAttacher, self).setUp()
        # do not attach circuits automatically
        yield self.tor.set_attacher(None, reactor)

    @defer.inlineCallbacks
    def test_create_circuit(self):
        # All relays are also exits in network/basic-025
        path = self.random_path()
        circ = yield self.attacher.create_circuit('127.0.0.1', 1234, path)
        self.failUnlessIsInstance(circ, Circuit)
        self.assertEqual(circ.path, path)
        yield circ.close()

    def test_attach_stream(self):
        target = random.choice(self.routers)
        stream = FakeStream(target_port=int(target.or_port),
                            target_host=target.ip)
        path = self.random_path()
        circ = self.attacher.create_circuit(stream.source_addr,
                                            stream.source_port, path)
        attached_circ = self.attacher.attach_stream(stream, None)
        self.assertEqual(circ, attached_circ)
        return self.failUnlessEqual(circ, attached_circ)

    def test_circuit_built(self):
        circuit = FakeCircuit()
        circuit.path = self.random_path()
        circuit.purpose = "GENERAL"
        circ_callback = defer.Deferred()
        self.attacher.waiting_circuits[circuit.id] = (circuit, circ_callback)
        self.attacher.circuit_built(circuit)
        circ_callback.addCallback(self.assertEqual, circuit)
        return circ_callback

    def test_circuit_failed(self):
        circuit = FakeCircuit()
        circuit.path = self.random_path()
        circuit.purpose = "GENERAL"
        circ_callback = defer.Deferred()
        self.attacher.waiting_circuits[circuit.id] = (circuit, circ_callback)
        self.attacher.circuit_failed(circuit, reason="reason")
        return self.failUnlessFailure(circ_callback, FakeCircuit).addCallback(
            self.failUnlessEqual, circuit)
