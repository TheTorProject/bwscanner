import json
from shutil import rmtree
from os.path import walk, join
from tempfile import mkdtemp

from twisted.trial import unittest
from twisted.internet import defer

from bwscanner.writer import ResultSink
from random import randint


class TestResultSink(unittest.TestCase):

    def test_send_multiple_chunk_size(self):
        self.tmpdir = mkdtemp()
        chunk_size = 10
        self.result_sink = ResultSink(self.tmpdir, chunk_size=chunk_size)
        test_data = {'test_method': 'test_send_chunk_size'}
        num_chunks = randint(121, 212)
        deferreds = []
        for _ in xrange(chunk_size * num_chunks):
            deferreds += [self.result_sink.send(test_data)]

        def validate(_, dirname, fnames):
            assert len(fnames) == num_chunks
            for fname in fnames:
                path = join(dirname, fname)
                with open(path, 'r') as testfile:
                    results = json.load(testfile)
                    for result in results:
                        assert 'test_method' in result
                        assert result['test_method'] == 'test_send_chunk_size'
        dl = defer.DeferredList(deferreds)
        dl.addCallback(lambda results: self.result_sink.end_flush())
        dl.addCallback(lambda results: walk(self.tmpdir, validate, None))
        return dl

    def test_send_chunk_size(self):
        self.tmpdir = mkdtemp()
        chunk_size = 10
        self.result_sink = ResultSink(self.tmpdir, chunk_size=chunk_size)
        test_data = {'test_method': 'test_send_chunk_size'}
        deferreds = []
        for _ in xrange(chunk_size):
            deferreds += [self.result_sink.send(test_data)]

        def validate(_, dirname, fnames):
            assert len(fnames) == 1
            for fname in fnames:
                path = join(dirname, fname)
                with open(path, 'r') as testfile:
                    results = json.load(testfile)
                    for result in results:
                        assert 'test_method' in result
                        assert result['test_method'] == 'test_send_chunk_size'
        dl = defer.DeferredList(deferreds)
        dl.addCallback(lambda results: self.result_sink.end_flush())
        dl.addCallback(lambda results: walk(self.tmpdir, validate, None))
        return dl

    def test_end_flush(self):
        self.tmpdir = mkdtemp()
        chunk_size = 10
        self.result_sink = ResultSink(self.tmpdir, chunk_size=chunk_size)
        test_data = {'test_method': 'test_send_chunk_size'}
        deferreds = []
        for _ in xrange(chunk_size + 3):
            deferreds += [self.result_sink.send(test_data)]

        def validate(_, dirname, fnames):
            # assert len(fnames) == 1
            for fname in fnames:
                path = join(dirname, fname)
                with open(path, 'r') as testfile:
                    results = json.load(testfile)
                    for result in results:
                        assert 'test_method' in result
                        assert result['test_method'] == 'test_send_chunk_size'
        dl = defer.DeferredList(deferreds)
        dl.addCallback(lambda results: self.result_sink.end_flush())
        dl.addCallback(lambda results: walk(self.tmpdir, validate, None))
        return dl

    def tearDown(self):
        def remove_tree(result):
            rmtree(self.tmpdir)
            return result
        return self.result_sink.current_task.addCallback(remove_tree)
