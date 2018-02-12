
from bwscanner.circuit import TwoHop
from test.template import TorTestCase


class TestCircuitGenerators(TorTestCase):

    def test_two_hop(self):
        all_r = set(self.routers)
        num_circuits = 0
        seen = set()
        for circuit in TwoHop(self.tor_state):
            assert len(circuit) == 2
            assert 'exit' in circuit[-1].flags
            num_circuits = num_circuits + 1
            seen.add(circuit[0])
        assert seen == all_r
        assert num_circuits == len(all_r)
