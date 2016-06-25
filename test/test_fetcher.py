from twisted.internet import defer, reactor
from twisted.internet.protocol import Protocol
from twisted.web.client import readBody
from twisted.web.resource import Resource
from twisted.web.server import Site

from txsocksx.errors import ConnectionRefused
from txtorcon.util import available_tcp_port

from bwscanner.fetcher import OnionRoutedTCPClientEndpoint, OnionRoutedAgent
from test.template import TorTestCase

import random

class MockProtocol(Protocol):
    def __init__(self):
        self.data = ""

    def buildProtocol(self, _):
        return self

    def dataReceived(self, data):
        self.data += data

    def connectionMade(self):
        self.transport.write("GET / HTTP/1.1\r\n")

class TestOnionRoutedTCPClientEndpoint(TorTestCase):
    @defer.inlineCallbacks
    def test_connect_tcp(self):
        endpoint = random.choice(self.routers)
        ore = OnionRoutedTCPClientEndpoint(endpoint.ip, int(endpoint.or_port),
                                           self.tor, self.random_path())
        proto = yield ore.connect(MockProtocol())
        self.failUnlessIsInstance(proto, MockProtocol)

    @defer.inlineCallbacks
    def test_connect_tcp_fail(self):
        ore = OnionRoutedTCPClientEndpoint('127.0.0.1', 3,
                                           self.tor, self.random_path())
        try:
            yield ore.connect(MockProtocol())
        except ConnectionRefused:
            pass

class TestOnionRoutedAgent(TorTestCase):
    @defer.inlineCallbacks
    def setUp(self):
        yield super(TestOnionRoutedAgent, self).setUp()
        class DummyResource(Resource):
            isLeaf = True
            def render_GET(self, request):
                return "%s" % request.method

        self.port = yield available_tcp_port(reactor)
        self.site = Site(DummyResource())
        self.test_service = yield reactor.listenTCP(self.port, self.site)

    @defer.inlineCallbacks
    def test_do_request(self):
        agent = OnionRoutedAgent(reactor, path=self.random_path(),
                                 state=self.tor)
        url = "http://127.0.0.1:{}".format(self.port)
        request = yield agent.request("GET", url)
        body = yield readBody(request)
        yield self.assertEqual(body, 'GET')

    @defer.inlineCallbacks
    def test_do_failing_request(self):
        agent = OnionRoutedAgent(reactor, path=self.random_path(),
                                 state=self.tor)

        url = "http://127.0.0.1:{}".format(3)
        try:
            yield agent.request("GET", url)
        except ConnectionRefused:
            pass

    @defer.inlineCallbacks
    def tearDown(self):
        yield super(TestOnionRoutedAgent, self).tearDown()
        yield self.test_service.stopListening()
