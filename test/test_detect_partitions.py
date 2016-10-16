
import hashlib
from twisted.trial import unittest

from bwscanner.partition_shuffle import lazy2HopCircuitGenerator


class PermutationsTests(unittest.TestCase):

    def test_shuffle_generator(self):
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
