#!/usr/bin/env python2.7

import hashlib
from math import sqrt

############ algorithms:

class yolo_prng():
  """Basic inefficient HMAC-based PRNG generator."""
  hash_output_length = 32 # for sha256
  hash_algorithm     ='sha256'
  def __init__(self, seed, purpose='', stream_index = 0):
    self.seed = seed
    self.stream_index = stream_index
  def next_bytes(self, length):
    # resume previous position, if given
    hmac_generation = self.stream_index / self.hash_output_length
    byte_offset     = self.stream_index % self.hash_output_length
    buf = ''
    bytes_to_read = length
    while len(buf) < length:
      current = hashlib.pbkdf2_hmac(
                  self.hash_algorithm,
                  self.seed,
                  str(hmac_generation),
                  iterations=1 )
      buf += current[ byte_offset : byte_offset + bytes_to_read ]
      bytes_to_read -= self.hash_output_length - byte_offset
      byte_offset = 0
      hmac_generation += 1
    self.stream_index += length
    return buf
  def next_bounded(self, maximum):
    """Returns values in the set [0 ; .. ; maximum]"""
    if 0 == maximum: return 0
    from math import ceil, log
    prng_bytes_to_read = int(ceil(log(1 + maximum, 256)))
    assert 0 < prng_bytes_to_read
    word = 1 + maximum # in the absense of do..while()
    while word >= maximum:
      prng_bytes = self.next_bytes(prng_bytes_to_read)
      # interpret them as an unsigned integer:
      word = int(prng_bytes.encode('hex'), 0x10)
      # adjust for modulo bias by discarding word if larger than our set:
      if word <= maximum or 0 == (1+maximum) % (256**prng_bytes_to_read):
        return word

def fisher_yates_shuffle(source, prng):
  """Implements the "inside-out" algorithm from Wikipedia:
     https://en.wikipedia.org/wiki/Fisher%E2%80%93Yates_shuffle#The_.22inside-out.22_algorithm"""
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
    if j == len(a):
      a.append(source[i])
    else:
      a.append(a[j])
      a[j] = source[i]
  return a

def pick_prime(number_of_relays, prng):
  """find a slightly random prime, using a fairly naive, exhaustive algorithm"""
  candidate = prng.next_bounded(1<<42)
  # make sure it's at least 42 bits (arbitrary number based on how long it takes to sieve on my machine)
  candidate += 1<<42
  assert candidate > number_of_relays
  # round up to nearest odd number:
  candidate += (candidate ^ 1) & 1
  while True:
    # next odd number:
    candidate += 2
    # check all odd numbers between 3 and sqrt(candidate)
    for x in range(3, 1 + int(sqrt(candidate)), 2):
      if candidate % x == 0: break
    else: # if no factors are found:
      return candidate

def pick_coordinates(i, maxx):
  """Turn an integer index into a coordinate pair"""
  assert i < maxx * maxx
  return (i % maxx, i / maxx)

############ set parameters:

# the ordered list of relays in the consensus:
tor_relays = ['A','B','C', 'E', 'F', 'G']

# the hash of the consensus (don't necessarily need to compute it here)
consensus_hash = hashlib.sha256('REPLACEME - whatever').digest()

# a secret random value shared between all nodes (site-specific):
shared_secret = hashlib.sha256('REPLACEME - fuck global observers').digest()

prng_seed = hashlib.pbkdf2_hmac(
                'sha256',
                consensus_hash,
                shared_secret, 
                iterations=1 )

############ initialize prng and shuffle

def shuffle_sets():
  shared_prng = yolo_prng(prng_seed, purpose = 'relay shuffle')

  shuffled_sets = map(lambda _: [], xrange(2)) # 2 == circuit length

  for hop_number in xrange(2): # 2 == circuit length
    # we shuffle the set of relays twice, to get two independent lists
    # (to spread the coordinates over more nodes)
    shuffled_sets[hop_number] = tuple(fisher_yates_shuffle(tor_relays, shared_prng))
  return shuffled_sets

shuffled_sets = shuffle_sets()

############ pick connection pairs:

def pair_generator(node_id = None, number_of_nodes = None):
  shared_prng = yolo_prng(prng_seed, purpose = 'pair generator')
  prime = pick_prime(len(tor_relays), shared_prng)
  elements = len(tor_relays) ** 2

  idx = 0
  indexes = []
  set_size = 1

  for offset in xrange(elements + 1):
    if offset % set_size == 0 or offset == elements:
      indexes = fisher_yates_shuffle(indexes, shared_prng)
      unique = 0
      for i in xrange(len(indexes)):
        a , b = pick_coordinates(indexes[i], len(tor_relays))
        x , y = shuffled_sets[0][a] , shuffled_sets[1][b]
        if x == y: continue
        unique += 1
        if unique % number_of_nodes == node_id:
          yield (x , y, node_id) # for real usage we'd probably discard node_id
      # come up with a random set size (we pop a small set of )
      set_size = 10 + number_of_nodes + shared_prng.next_bounded(1000)
      indexes = []
    idx = (idx + prime) % elements
    indexes.append(idx)
    if offset == elements: return

############ sample usage:

pairg = pair_generator(node_id = 0, number_of_nodes = 3)
try:
  while True:
    print pairg.next()
except StopIteration: pass

for x in pair_generator(node_id = 1, number_of_nodes = 3):
  print x

for x in pair_generator(node_id = 2, number_of_nodes = 3):
  print x

