"""
Classes used for choosing relay circuit paths
"""
import operator
import random

class CircuitGenerator(object):
    def __init__(self, state):
        self.state = state
        self.relays = list(set(state.routers.values()))
        self.exits = [relay for relay in self.relays if self.is_valid_exit(relay)]

    def __iter__(self):
        return self

    def next(self):
        raise NotImplementedError

    @staticmethod
    def is_valid_exit(relay):
        """
        Check that has the correct flags and exit policy for exiting

        TODO: Check the exit policy
        """
        return ('exit' in relay.flags and 'badexit' not in relay.flags)


class ExitScan(CircuitGenerator):
    """
    Returns a generator that yields a set of circuits.

    The set of circuits contain each exit relay from a snapshot
    of the consensus in the exit position once. The first and
    second hops are selected randomly.
    """
    def __init__(self, state):
        super(ExitScan, self).__init__(state)
        random.shuffle(self.exits)

        def circuit_generator():
            """
            Pick two other relays for a circuit while being sure not
            to use the exit relay more than once.
            """
            for exit_relay in self.exits:
                # Sample an extra relay in case one of the choices is the exit.
                candidate_relays = random.sample(self.relays, 3)
                if exit_relay in candidate_relays:
                    candidate_relays.remove(exit_relay)
                yield candidate_relays[0:2] + [exit_relay]

        self._circgen = circuit_generator()

    def next(self):
        return self._circgen.next()


class TwoHop(CircuitGenerator):
    """
    Select two hop circuits with the relay to be measured and a random exit
    relay of similar bandwidth.
    """
    def __init__(self, state, partitions=1, this_partition=0, slice_width=50):
        """
        TwoHop can be called multiple times with different partition
        values to produce slices containing a subset of the relays. These
        partitions are not grouped by bandwidth.
        """
        super(TwoHop, self).__init__(state)
        self._slice_width = slice_width
        self.exits.sort(key=operator.attrgetter('bandwidth'))

        def circuit_generator():
            """
            Select relays from the partition in a random order. Also
            choose an exit relay of similar bandwidth for the circuit
            """
            num_relays = len(self.relays)
            for i in random.sample(range(this_partition, num_relays, partitions),
                                   num_relays):
                relay = self.relays[i]
                yield relay, self.exit_by_bw(relay)

        self._circgen = circuit_generator()

    def exit_by_bw(self, relay):
        """
        Find an exit relay with a similar bandwidth to the `relay` being
        measured.

        We can select a slower bandwidth exit relay if we don't have enough
        faster exit relays available to create a full slice. We try to
        pick an exit from a full width slice if possible.

        XXX: Is it a problem to measure the fastest relays against some slower
             relays? Will the measured BW approach a limit?
        """
        num_exits = len(self.exits)
        for i, exit in enumerate(self.exits):
            # Skip exit if it's slower, and we have more exits left to choose.
            if (exit.bandwidth < relay.bandwidth) and (i != num_exits):
                continue

            exit_slice = self.exits[i:i+self._slice_width]
            exits_needed = self._slice_width - len(exit_slice)

            # There isn't enough exits, pick some slower exits for this slice.
            if exits_needed:
                slice_start = max(0, i-exits_needed)
                exit_slice = self.exits[slice_start:i] + exit_slice

            if relay in exit_slice:
                exit_slice.remove(relay)
            return random.choice(exit_slice)

        raise ValueError("Did not find a suitable exit relay to build this "
                         "circuit.")

    def next(self):
        return self._circgen.next()


class ThereAndBackAgain(CircuitGenerator):
    def __init__(self, state, entry_exit_relay):
        super(ThereAndBackAgain, self).__init__(state)
        random.shuffle(self.relays)

        def circuit_generator():
            """
            Select a three hop path with the scanned relay as a middle relay.
            """
            for relay in self.relays:
                yield [entry_exit_relay,
                       relay,
                       entry_exit_relay]

        self._circgen = circuit_generator()

    def next(self):
        return self._circgen.next()


class FullyConnected(CircuitGenerator):
    """
    Yield Two Hop circuits for every possible pair of relays

    Each pair will only be selected once, the reverse pairing will
    not also be produced.
    """
    def __init__(self, state, this_partition=0, partitions=1):
        super(FullyConnected, self).__init__(state)

        def circuit_generator():
            n = len(self.relays)
            n_pairs = n*(n-1)/2
            key = 0
            for k in range(this_partition, n_pairs, partitions):
                (i, j) = to_pair(arbitrary_domain_perm(key, k, n_pairs), n)
                yield (self.relays[i], self.relays[j])
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
