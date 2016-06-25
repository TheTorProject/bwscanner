
from twisted.trial import unittest
from twisted.internet import defer, task
from twisted.test import proto_helpers

from txtorcon import TorControlProtocol
from txtorcon.router import hashFromHexId

from bwscanner.condor import ResultSink, ProbeAll2HopCircuits
from bwscanner.circuit import FullyConnected, to_pair


class ResultSinkTests(unittest.TestCase):

    def test_basic(self):
        sink = ResultSink('.', chunk_size=3)
        d = sink.set_hook("write")
        sink.send({"meow":1})
        self.failUnlessEqual(sink.current_log_num, 0)
        sink.send({"meow":2})
        sink.send({"meow":3})
        sink.send({"meow":4})
        d.addCallback(lambda ign: self.failUnlessEqual(sink.current_log_num, 1))
        d.addCallback(lambda ign: self.failUnlessEqual(sink.writing, False))
        def send_more(result):
            d2 = sink.set_hook("write")
            sink.send({"meow":5})
            sink.send({"meow":6})
            sink.send({"meow":7})
            return d2
        d.addCallback(send_more)
        d.addCallback(lambda ign: self.failUnlessEqual(sink.current_log_num, 2))
        d.addCallback(lambda ign: self.failUnlessEqual(sink.writing, False))
        return d

    def test_end_flush(self):
        sink = ResultSink('.', chunk_size=3)
        sink.send({"meow":1})
        sink.send({"meow":2})
        sink.send({"meow":3})
        sink.send({"meow":4})
        d = defer.succeed(None)
        def ending(result):
            return sink.end_flush()
        d.addCallback(ending)
        d.addCallback(lambda ign: self.failUnlessEqual(sink.current_log_num, 1))
        d.addCallback(lambda ign: self.failUnlessEqual(sink.writing, False))
        return d


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
        print "d %r" % (d,)
        d.addCallback(self._find_circuit_after_extend)
        return d

class FakeRouter:

    def __init__(self, i):
        self.id_hex = i
        self.flags = []

class ProbeTests(unittest.TestCase):

    def test_basic(self):
        routers = {}
        for x in range(3):
            routers.update({"router%r" % (x,): FakeRouter("$%040d" % x)})

        tor_state = FakeTorState(routers)
        tor_state._attacher_error = lambda f: f
        tor_state.transport = proto_helpers.StringTransport()

        clock = task.Clock()
        log_dir = "."
        stop_hook = defer.Deferred()
        def stopped():
            print "stopped"
            stop_hook.callback(None)
        probe = ProbeAll2HopCircuits(tor_state, clock, log_dir, stopped)
        probe.run_scan()
        clock.advance(10)
        clock.advance(10)
        clock.advance(10)
        clock.advance(10)
        clock.advance(10)
        clock.advance(10)
        clock.advance(10)
        clock.advance(10)
        clock.advance(10)
        clock.advance(10)
        return stop_hook

class PermutationsTests(unittest.TestCase):

    def test_to_pair(self):
        n = 5
        pairs = [to_pair(x, n) for x in range(n*(n-1)/2)]
        self.failUnlessEqual(pairs, [(0, 1), (0, 2), (0, 3), (0, 4), (1, 2), (1, 3), (1, 4), (2, 3), (2, 4), (3, 4)])

    def test_permutations(self):
        class FakeTorState(object):
            def __init__(self, routers):
                self.routers = routers
        routers = {
            "relay1":FakeRouter(123),
            "relay2":FakeRouter(234),
            "relay3":FakeRouter(345),
            "relay4":FakeRouter(456),
        }
        tor_state = FakeTorState(routers)
        jenny = FullyConnected(tor_state)
        results = []
        for i in jenny:
            results.append(i)
        self.failUnlessEqual(len(results), 6)
        self.failUnless((routers["relay1"], routers["relay2"]) in results)
        self.failUnless((routers["relay2"], routers["relay3"]) in results)
        self.failUnless((routers["relay1"], routers["relay3"]) in results)
        self.failUnless((routers["relay1"], routers["relay4"]) in results)
        self.failUnless((routers["relay2"], routers["relay4"]) in results)
        self.failUnless((routers["relay3"], routers["relay4"]) in results)
