import random

class CircuitGenerator(object):
    def __init__(self, state):
        self.state = state

    def __iter__(self):
        return self

    def next(self):
        raise NotImplementedError

class ExitScan(CircuitGenerator):
    """
    Returns a generator that yields a set of circuits.

    The set of circuits contain each exit relay from a snapshot
    of the consensus in the exit position once. The first and
    second hops are selected randomly.
    """
    def __init__(self, state):
        super(ExitScan, self).__init__(state)
        self.exits = [r for r in list(set(self.state.routers.values()))
                      if 'exit' in r.flags and 'badexit' not in r.flags]
        random.shuffle(self.exits)

        def circuit_generator():
            routers = list(set(self.state.routers.values()))
            for exitr in self.exits:
                path = [random.choice(routers) for _ in xrange(2)]
                path.append(exitr)
                yield path

        self._circgen = circuit_generator()

    def next(self):
        return self._circgen.next()

class TwoHop(CircuitGenerator):
    def __init__(self, state, partitions=1, this_partition=0, slice_width=50):
        super(TwoHop, self).__init__(state)
        # Take a snapshot of the relay identities and shuffle them
        self._slice_width = slice_width
        self._relays = list(set(state.routers.values()))
        self._exits = [r for r in self._relays
                       if 'exit' in r.flags and 'badexit' not in r.flags]
        self._exits.sort(cmp=lambda x, y: cmp(x.bandwidth, y.bandwidth))

        def circuit_generator():
            n = len(self._relays)
            first_hops = [i for i in range(this_partition, n, partitions)]
            random.shuffle(first_hops)
            for i in first_hops:
                yield self._relays[i], self.exit_by_bw(self._relays[i])
        self._circgen = circuit_generator()

    def exit_by_bw(self, relay):
        # We take a snapshot of the consensus by copying the routers list!
        # It does _not_ verify that the relay exits to ports 80, 443. FIXME?
        for i, ex in enumerate(self._exits):
            if ex.bandwidth >= relay.bandwidth:
                range_min = max(0, i - self._slice_width)
                range_max = min(len(self._exits), i + self._slice_width)
                if range_max == len(self._exits):
                    range_min = range_max - self._slice_width
                elif range_min == 0:
                    range_max = range_min + self._slice_width
                relay_slice = self._exits[range_min:range_max]
                if relay in relay_slice:
                    relay_slice.remove(relay)
                return random.choice(relay_slice)

    def next(self):
        return self._circgen.next()

class ThereAndBackAgain(CircuitGenerator):
    def __init__(self, state, entry_exit_relay):
        super(ThereAndBackAgain, self).__init__(state)
        self._relays = list(set(self.state.routers.values()))
        random.shuffle(self._relays)
        def circuit_generator():
            for relay in self._relays:
                yield [entry_exit_relay,
                       relay,
                       entry_exit_relay]
        self._circgen = circuit_generator()

    def next(self):
        return self._circgen.next()

class FullyConnected(CircuitGenerator):
    def __init__(self, state, partitions=1, thispartition=0):
        super(FullyConnected, self).__init__(state)
        self._relays = sorted(set(state.routers.values()))
        def circuit_generator():
            n = len(self._relays)
            n_pairs = n*(n-1)/2
            key = 0
            for k in range(thispartition, n_pairs, partitions):
                (i, j) = to_pair(arbitrary_domain_perm(key, k, n_pairs), n)
                yield (self._relays[i], self._relays[j])
        self._circgen = circuit_generator()

    def next(self):
        return self._circgen.next()

def arbitrary_domain_perm(key, x, n):
    return (x + key) % n

def to_pair(x, n):
    """Pick the xth (0-based) pair out of the n*(n-1)/2 possible pairs."""

    #  0    <= x <  n-1  =>  i = 0
    #  n-1  <= x < 2n-3  =>  i = 1
    # 2n-3  <= x < 3n-6  =>  i = 2
    # 3n-6  <= x < 4n-10 =>  i = 3
    # 4n-10 <= x < 5n-15 =>  i = 4

    # k*n - k*(k+1)/2 <= x < (k+1)*n - (k+1)*(k+2)/2 => i = k
    lb = 0
    ub = n-1
    while True:
        i = (lb+ub) // 2
        too_high = (x < i*n - i*(i+1)/2)
        too_low = (x >= (i+1)*n - (i+1)*(i+2)/2)
        if too_low:
            lb = i+1
        elif too_high:
            ub = i-1
        else:
            # just right :-)
            break

    assert i*n - i*(i+1)/2 <= x
    assert x < (i+1)*n - (i+1)*(i+2)/2

    j = i+1 + x - (i*n - i*(i+1)/2)
    return (i, j)
