
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
            print "partition %d" % partition_id
            partition = [circuit for circuit in
                         lazy2HopCircuitGenerator(relays, partition_id, partitions, prng_seed)]
            for c in partition:
                print c
            print "partition size %d" % len(partition)
            all_partitions += partition
        print "%d == %d" % (len(all_partitions), (total_relays**2)-total_relays)
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
            print "partition %d" % partition_id
            partition = [circuit for circuit in
                         lazy2HopCircuitGenerator(relays, partition_id, partitions, prng_seed)]
            print "partition size %d" % len(partition)
            all_partitions += partition
        print "%d == %d" % (len(all_partitions), (total_relays**2)-total_relays)
        self.assertEqual(len(all_partitions), (total_relays**2)-total_relays)


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
        print "build circuit"
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

        consensus = ""
        for relay in [str(relay.id_hex) for relay in relays]:
            consensus += relay + ","
        consensus_hash = hashlib.sha256(consensus).digest()
        shared_secret_hash = hashlib.sha256(secret).digest()
        prng_seed = hashlib.pbkdf2_hmac('sha256', consensus_hash, shared_secret_hash, iterations=1)
        circuit_generator = lazy2HopCircuitGenerator(relays, this_partition, partitions, prng_seed)
        log_chunk_size = 1000
        max_concurrency = 5
        probe = ProbeAll2HopCircuits(tor_state, clock, log_dir, stopped,
                                     partitions, this_partition,
                                     build_duration, circuit_timeout, circuit_generator,
                                     log_chunk_size, max_concurrency)
        probe.start()
        for _ in range(len(relays)**2 - len(relays)):
            try:
                clock.advance(.2)
            except AlreadyCalled:
                pass
        return stop_hook
