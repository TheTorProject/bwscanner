#!/usr/bin/env python

from pyblake2 import blake2b
from math import sqrt, ceil, log
from struct import unpack


class yolo_prng():
    """Basic inefficient HMAC-based PRNG generator."""
    hash_output_length = 32
    pack_table = {1:'B', 2:'H', 3:'>I', 4:'I', 5:'>Q', 6:'>Q'} # bigendian if we prepend 0x00
    prepend_table = {1:'', 2:'', 3:'\x00', 4: '', 5: '\x00\x00\x00', 6: '\x00\x00'}

    def __init__(self, seed, stream_index=0):
        self.seed = seed
        self.stream_index = stream_index
        self.cached_hmac_generation = None
        self.compute_current()

    def compute_current(self):
        this_hmac_generation = self.stream_index / self.hash_output_length
        if this_hmac_generation > self.cached_hmac_generation:
            b = blake2b(data=self.seed, key=str(this_hmac_generation), digest_size=self.hash_output_length)
            self.current = b.digest()
            self.cached_hmac_generation = this_hmac_generation

    def next_bytes(self, length):
        # resume previous position, if given
        buf = ''
        total_bytes_read = 0
        # old_stream_idx = self.stream_index
        byte_offset = self.stream_index % self.hash_output_length
        old_stream_idx = self.stream_index
        if byte_offset != 0:
            total_bytes_read = self.hash_output_length - byte_offset
            if total_bytes_read > length:
                self.stream_index += length
                return self.current[byte_offset:byte_offset+length]
            buf += self.current[byte_offset : ]
            self.stream_index += total_bytes_read
        for i in xrange((length-total_bytes_read) / self.hash_output_length):
            self.compute_current()
            buf += self.current
            self.stream_index += self.hash_output_length
            total_bytes_read += self.hash_output_length
        self.compute_current()
        if total_bytes_read < length:
            byte_offset = self.stream_index % self.hash_output_length
            bytes_to_read = length - total_bytes_read
            assert bytes_to_read < self.hash_output_length
            buf += self.current[:bytes_to_read]
            self.stream_index += bytes_to_read
            total_bytes_read += bytes_to_read
        assert total_bytes_read == length
        assert old_stream_idx + total_bytes_read == self.stream_index
        return buf

    def next_bounded(self, maximum):
        """Returns values in the set [0 ; .. ; maximum]"""
        # XXX this is slow as fuck because we end up rejecting tons of numbers
        if 0 == maximum:
            return 0

        prng_bytes_to_read = int(ceil(log(1 + maximum, 256)))
        assert 9 > prng_bytes_to_read
        this_pack_fmt = self.pack_table[prng_bytes_to_read] # find the best fit
        word = 1 + maximum  # in the absense of do..while()
        # rejected_count = 0
        while word >= maximum:
            prng_bytes = self.next_bytes(prng_bytes_to_read)
            # interpret them as an unsigned integer:
            #word = int(prng_bytes.encode('hex'), 0x10)
            word = unpack(this_pack_fmt,
                        self.prepend_table[prng_bytes_to_read] + prng_bytes
            )[0] & ((1<<(8*prng_bytes_to_read))-1)

            # TODO actually yeah fuck that, unless we bother counting bits, that's
            # a major bottleneck, so let's accept biased output after some attempts.
            #if word <= maximum or rejected_count > 3: # or 0 == (1+maximum) % (256**prng_bytes_to_read):
            return word % (1+maximum)
            # rejected_count += 1

def fisher_yates_shuffle(source, prng):
    """
    Implements the "inside-out" algorithm from Wikipedia:
    https://en.wikipedia.org/wiki/Fisher%E2%80%93Yates_shuffle#The_.22inside-out.22_algorithm
    """
    # To initialize an array a of n elements to a randomly shuffled copy of source, both 0-based:
    #  for i from 0 to n - 1 do
    #      j <- random integer such that 0 <= j <= i
    #      if j != i
    #          a[i] <- a[j]
    #      a[j] <- source[i]

    n = len(source)
    a = []
    for i in xrange(n):
        # j <- random integer such that 0 <= j <= i
        j = prng.next_bounded(i)
        assert 0 <= j and j <= i
        if j == i:
            a.append(source[i])
        else:
            a.append(a[j])
            a[j] = source[i]
    return a


def pick_prime(number_of_relays, prng):
    """
    find a slightly random prime, using a fairly naive, exhaustive algorithm
    """
    candidate = prng.next_bounded(1 << 42)
    # make sure it's at least 42 bits (arbitrary number based on how
    # long it takes to sieve on my machine)
    candidate += 1 << 42
    assert candidate > number_of_relays
    # round up to nearest odd number:
    candidate += (candidate ^ 1) & 1
    while True:
        # next odd number:
        candidate += 2
        # check all odd numbers between 3 and sqrt(candidate)
        for x in xrange(3, 1 + int(sqrt(candidate)), 2):
            if candidate % x == 0:
                break
        else:  # if no factors are found:
            return candidate


def pick_coordinates(i, maxx):
    """
    Turn an integer index into a coordinate pair
    """
    assert i < maxx * maxx
    return (i % maxx, i / maxx)


def shuffle_sets(relays, prng_seed):
    shared_prng = yolo_prng(prng_seed)
    shuffled_sets = map(lambda _: [], xrange(2))  # 2 == circuit length
    for hop_number in xrange(2):  # 2 == circuit length
        # we shuffle the set of relays twice, to get two independent lists
        # (to spread the coordinates over more nodes)
        shuffled_sets[hop_number] = tuple(fisher_yates_shuffle(relays, shared_prng))
    return shuffled_sets


def lazy2HopCircuitGenerator(relays, this_partition, partitions, prng_seed):
    """
    factory of lazy generator for shuffled 2-hop circuits with low cpu
    and memory requirements and a partitioning scheme to facilitate
    parallelizing the scan of the entire shuffled set.

    relays: the total list of relays for a given Tor consensus
    this_partition: the partition id corresponding to this generator
    partitions: total number of partitions
    prng_seed: prnd seed which is a shared secret for all scanner hosts
    """
    shared_prng = yolo_prng(prng_seed)
    relays_len = len(relays)
    prime = pick_prime(relays_len, shared_prng)
    elements = relays_len ** 2
    idx = 0
    indexes = []
    set_size = 200
    shuffled_sets = shuffle_sets(relays, prng_seed)

    for offset in xrange(elements + 1):
        if offset % set_size == 0 or offset == elements:
            indexes = fisher_yates_shuffle(indexes, shared_prng)
            unique = 0
            for i in xrange(len(indexes)):
                a, b = pick_coordinates(indexes[i], relays_len)
                x, y = shuffled_sets[0][a], shuffled_sets[1][b]
                if x == y:
                    continue
                unique += 1
                if unique % partitions == this_partition:
                    yield (x, y)
            # come up with a random set size (we pop a small set of )
            set_size = 100 + partitions + shared_prng.next_bounded(255)
            indexes = []
        idx = (idx + prime) % elements
        indexes.append(idx)
        if offset == elements:
            return
