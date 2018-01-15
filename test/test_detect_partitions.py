
import hashlib

from twisted.trial import unittest
from twisted.test import proto_helpers
from twisted.internet import defer, task
from twisted.internet.error import AlreadyCalled
from txtorcon import TorControlProtocol
from txtorcon.router import hashFromHexId

from bwscanner.partition_scan import ProbeAll2HopCircuits
from bwscanner.partition_shuffle import lazy2HopCircuitGenerator


class FakeRouter:

    def __init__(self, name, i):
        self.name = name
        self.id_hex = i
        self.flags = []

    def __str__(self):
        return self.name


class PermutationsGeneratorTests(unittest.TestCase):

    def test_shuffle_generator1(self):
        total_relays = 5
        relays = [x for x in range(total_relays)]
        partitions = 3
        consensus_hash = hashlib.sha256('REPLACEME consensus hash').digest()
        shared_secret = hashlib.sha256('REPLACEME shared secret').digest()
        prng_seed = hashlib.pbkdf2_hmac('sha256', consensus_hash, shared_secret, iterations=1)
        all_partitions = []
        for partition_id in range(partitions):
            partition = [circuit for circuit in
                         lazy2HopCircuitGenerator(relays, partition_id, partitions, prng_seed)]
            all_partitions += partition
        self.assertEqual(len(all_partitions), (total_relays**2)-total_relays)

    def test_shuffle_generator2(self):
        total_relays = 80
        relays = [x for x in range(total_relays)]
        partitions = 4
        consensus_hash = hashlib.sha256('REPLACEME consensus hash').digest()
        shared_secret = hashlib.sha256('REPLACEME shared secret').digest()
        prng_seed = hashlib.pbkdf2_hmac('sha256', consensus_hash, shared_secret, iterations=1)
        all_partitions = []
        for partition_id in range(partitions):
            partition = [circuit for circuit in
                         lazy2HopCircuitGenerator(relays, partition_id, partitions, prng_seed)]
            all_partitions += partition
        self.assertEqual(len(all_partitions), (total_relays**2)-total_relays)

    def test_permutations(self):
        total_relays = 40
        routers = []
        for n in range(total_relays):
            routers.append("relay%d" % n)
        this_partition = 0
        partitions = 3

        consensus_hash = hashlib.sha256('REPLACEME consensus hash').digest()
        shared_secret = hashlib.sha256('REPLACEME shared secret').digest()
        prng_seed = hashlib.pbkdf2_hmac('sha256', consensus_hash, shared_secret, iterations=1)
        circuit_generator = lazy2HopCircuitGenerator(routers, this_partition,
                                                     partitions, prng_seed)
        circuits = map(lambda x: (str(x[0]), str(x[1])), [circuit for circuit in circuit_generator])
        expected = [('relay17', 'relay25'), ('relay10', 'relay26'), ('relay8', 'relay3'),
                    ('relay20', 'relay37'), ('relay7', 'relay26'), ('relay29', 'relay28'),
                    ('relay12', 'relay38'), ('relay7', 'relay14'), ('relay2', 'relay4'),
                    ('relay16', 'relay3')]
        self.failUnlessEqual(circuits[:10], expected)


class FakeTorState(object):

    def __init__(self, routers):
        self.routers = routers
        self.protocol = TorControlProtocol()
        self.protocol.connectionMade = lambda: None
        self.protocol.transport = proto_helpers.StringTransport()
        self.protocol.makeConnection(self.protocol.transport)

    def _find_circuit_after_extend(self, x):
        return defer.succeed(None)

    def build_circuit(self, routers=None, using_guards=True):
        cmd = "EXTENDCIRCUIT 0 "
        first = True
        for router in routers:
            if first:
                first = False
            else:
                cmd += ','
            if isinstance(router, basestring) and len(router) == 40 \
               and hashFromHexId(router):
                cmd += router
            else:
                cmd += router.id_hex[1:]
        d = self.protocol.queue_command(cmd)
        d.addCallback(self._find_circuit_after_extend)
        return d


class ProbeTests(unittest.TestCase):

    def test_basic(self):
        routers = {}
        for x in range(30):
            name = "$%040d" % x
            routers.update({"router%r" % (x,): FakeRouter(name, name)})

        tor_state = FakeTorState(routers)
        tor_state._attacher_error = lambda f: f
        tor_state.transport = proto_helpers.StringTransport()

        clock = task.Clock()
        log_dir = "."
        stop_hook = defer.Deferred()

        def stopped():
            stop_hook.callback(None)
        relays = routers.values()
        secret = hashlib.sha256('REPLACEME shared secret').digest()
        partitions = 3
        this_partition = 0
        build_duration = .2
        circuit_timeout = 10
        probe = ProbeAll2HopCircuits(tor_state, clock, log_dir, stopped,
                                     relays, secret, partitions, this_partition,
                                     build_duration, circuit_timeout)
        probe.start()
        for _ in range(len(relays)**2 - len(relays)):
            try:
                clock.advance(.2)
            except AlreadyCalled:
                pass
        return stop_hook
