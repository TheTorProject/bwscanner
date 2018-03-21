"""
Classes used for choosing relay circuit paths
"""
import operator
import random

from bwscanner.logger import log


def is_valid_exit(relay):
    """
    Check that has the correct flags and exit policy for exiting

    TODO: Check the exit policy
    """
    is_exit = ('exit' in relay.flags and 'badexit' not in relay.flags)
    return is_exit and 'authority' not in relay.flags


def random_path_to_exit(exit_relay, relays):
    """
    Choose a random path to the specified exit relay
    """
    # Sample an extra relay in case one of the choices is the exit.
    candidate_relays = random.sample(relays, 3)
    if exit_relay in candidate_relays:
        candidate_relays.remove(exit_relay)
    return candidate_relays[0:2] + [exit_relay]


class CircuitGenerator(object):
    def __init__(self, state):
        self.state = state
        self.relays = list(set(r for r in state.routers.values() if r))
        self.exits = [relay for relay in self.relays if is_valid_exit(relay)]

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
        random.shuffle(self.exits)

        def circuit_generator():
            """
            Pick two other relays for a circuit while being sure not
            to use the exit relay more than once.
            """
            for exit_relay in self.exits:
                yield random_path_to_exit(exit_relay, self.relays)

        self._circgen = circuit_generator()

    def next(self):
        return self._circgen.next()


class TwoHopDeprecated(CircuitGenerator):
    """
    Select two hop circuits with the relay to be measured and a random exit
    relay of similar bandwidth.
    """
    def __init__(self, state, partitions=1, this_partition=1, slice_width=50):
        """
        TwoHop can be called multiple times with different partition
        values to produce slices containing a subset of the relays. These
        partitions are not grouped by bandwidth.
        """
        super(TwoHopDeprecated, self).__init__(state)
        self._slice_width = slice_width
        self.exits.sort(key=operator.attrgetter('bandwidth'))

        def circuit_generator():
            """
            Select relays from the partition in a random order. Also
            choose an exit relay of similar bandwidth for the circuit
            """
            num_relays = len(self.relays)
            relay_subset = range(this_partition-1, num_relays, partitions)
            log.info("Performing a measurement scan with {count} relays.", count=len(relay_subset))

            # Choose relays in a random order fromm the relays in this partition set.
            for i in random.sample(relay_subset, len(relay_subset)):
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


class TwoHop(CircuitGenerator):
    """
    Select two hop circuits with the relay to be measured and a random exit
    relay of similar bandwidth in a similar way to Torflow.
    """
    def __init__(self, state, partitions=1, this_partition=1, slice_width=50):
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
            Select relays from the partition in a random order.
            """
            num_relays = len(self.relays)
            relay_partition = range(this_partition-1, num_relays, partitions)
            log.info("Performing a measurement scan with {count} relays.",
                     count=len(relay_partition))
            # Choose relays in a random order from the relays in this
            # partition set.
            relays = [self.relays[i] for i
                      in random.sample(relay_partition, len(relay_partition))]

            # order partition by bandwidth and divide it in 50 relays slices
            relays.sort(key=operator.attrgetter('bandwidth'))
            slices = [relays[i:i + self._slice_width] for i in
                      range(0, len(relays), self._slice_width)]
            log.debug("Using {num_slices} slices of width {slice_width}",
                      num_slices=len(slices), slice_width=self._slice_width)
            # for every slice
            for s in slices:
                exits = [e for e in s if is_valid_exit(e)]
                for i in range(0, len(s)):
                    # take a random relay from the slice
                    relay = random.choice(s)
                    # remove it from the slice so it is not chosen again
                    s.remove(relay)
                    # take a random exit from the slice
                    exit = random.choice([e for e in exits if e is not relay])
                    # but do not remove it as it can be used again
                    log.debug("Chosen relay and exit.")
                    yield relay, exit

        self._circgen = circuit_generator()

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
