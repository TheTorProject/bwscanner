from random import randint
from bwscanner.circuit import ExitScan, TwoHop, FullyConnected
from test.template import TorTestCase

class TestCircuitGenerators(TorTestCase):
    def test_exit_scan(self):
        all_exits = set(self.exits)
        num_circuits = 0
        seen = set()
        for circuit in ExitScan(self.tor):
            assert len(circuit) == 3
            assert 'exit' in circuit[-1].flags
            seen.add(circuit[-1])
            num_circuits = num_circuits + 1
        assert all_exits == seen
        assert num_circuits == len(all_exits)

    def test_two_hop(self):
        all_r = set(self.routers)
        num_circuits = 0
        seen = set()
        for circuit in TwoHop(self.tor):
            assert len(circuit) == 2
            assert 'exit' in circuit[-1].flags
            num_circuits = num_circuits + 1
            seen.add(circuit[0])
        assert seen == all_r
        assert num_circuits == len(all_r)

    def test_there_and_back_again(self):
        pass

    def test_fully_connected_single(self):
        # this will take a while to run
        circuits = {}
        expand_circuit_generator(FullyConnected(self.tor), circuits)

        for neighbors in circuits.itervalues():
            assert len(neighbors) == len(self.routers)
        assert len(circuits.keys()) == len(self.routers)

    def test_fully_connected_parts(self):
        n_parts = randint(3, 27)
        generators = [FullyConnected(self.tor, this_partition=i,
                                     partitions=n_parts) for i in xrange(n_parts)]
        circuits = {}
        for generator in generators:
            expand_circuit_generator(generator, circuits)

        for neighbors in circuits.itervalues():
            assert len(neighbors) == len(self.routers)
        assert len(circuits.keys()) == len(self.routers)

def expand_circuit_generator(circuit_generator, circuits):
    """
    Update a dictionary from a circuit generator.

    The dictionary tracks which routers have been present
    in circuits together.
    """
    for circuit in circuit_generator:
        for relay in circuit:
            circuits.setdefault(relay, set(circuit)).update(circuit)
