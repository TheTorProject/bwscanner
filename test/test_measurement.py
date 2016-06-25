from twisted.internet import defer, reactor
from twisted.web.resource import Resource
from twisted.web.server import Site
from txtorcon.util import available_tcp_port
from bwscanner.attacher import setconf_fetch_all_descs
from bwscanner.measurement import BwScan
from os.path import walk, join
from test.template import TorTestCase
from tempfile import mkdtemp

import json
from shutil import rmtree

class TestBwscan(TorTestCase):
    @defer.inlineCallbacks
    def setUp(self):
        yield super(TestBwscan, self).setUp()
        yield setconf_fetch_all_descs(self.tor)

        class DummyResource(Resource):
            isLeaf = True
            def render_GET(self, request):
                size = request.uri.split('/')[-1]
                if 'k' in size:
                    size = int(size[:-1])*(2**10)
                elif 'M' in size:
                    size = int(size[:-1])*(2**20)
                return 'a'*size

        self.port = yield available_tcp_port(reactor)
        self.test_service = yield reactor.listenTCP(
            self.port, Site(DummyResource()))

    def test_scan_chutney(self):
        # check that each run is producing the same input set!
        self.tmp = mkdtemp()
        scan = BwScan(self.tor, reactor, self.tmp)
        scan.baseurl = 'http://127.0.0.1:{}'.format(self.port)
        def check_all_routers_measured(_, dirname, fnames):
            all_done = set([r.id_hex for r in self.routers])
            measured = set()
            for fname in fnames:
                path = join(dirname, fname)
                with open(path, 'r') as testfile:
                    for measurement in json.load(testfile):
                        for router in measurement['path']:
                            measured.add(str(router))
            # check that every router has been measured at least once
            assert measured == all_done

        return scan.run_scan().addCallback(
            lambda ign: walk(self.tmp, check_all_routers_measured, None)
            )

    @defer.inlineCallbacks
    def tearDown(self):
        yield super(TestBwscan, self).tearDown()
        yield self.test_service.stopListening()
        rmtree(self.tmp)
