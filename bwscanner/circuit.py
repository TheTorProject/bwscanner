
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
