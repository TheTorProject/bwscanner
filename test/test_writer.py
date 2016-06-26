import json
from shutil import rmtree
from os.path import walk, join
from twisted.trial import unittest
from tempfile import mkdtemp

from bwscanner.writer import ResultSink
from random import randint


class TestResultSink(unittest.TestCase):

    def test_send_multiple_chunk_size(self):
        self.tmpdir = mkdtemp()
        chunk_size = 10
        result_sink = ResultSink(self.tmpdir, chunk_size=chunk_size)
        test_data = {'test_method': 'test_send_chunk_size'}
        num_chunks = randint(121, 212)
        for _ in xrange(chunk_size*num_chunks):
            result_sink.send(test_data)

        def validateoutput(_, dirname, fnames):
            assert len(fnames) == num_chunks
            for fname in fnames:
                path = join(dirname, fname)
                with open(path, 'r') as testfile:
                    results = json.load(testfile)
                    for result in results:
                        assert 'test_method' in result
                        assert result['test_method'] == 'test_send_chunk_size'
        return result_sink.end_flush().addCallback(
            lambda results: walk(self.tmpdir, validateoutput, None)
            )

    def test_send_chunk_size(self):
        self.tmpdir = mkdtemp()
        chunk_size = 10
        result_sink = ResultSink(self.tmpdir, chunk_size=chunk_size)
        test_data = {'test_method': 'test_send_chunk_size'}
        for _ in xrange(chunk_size):
            result_sink.send(test_data)

        def validateoutput(_, dirname, fnames):
            assert len(fnames) == 1
            for fname in fnames:
                path = join(dirname, fname)
                with open(path, 'r') as testfile:
                    results = json.load(testfile)
                    for result in results:
                        assert 'test_method' in result
                        assert result['test_method'] == 'test_send_chunk_size'
        return result_sink.end_flush().addCallback(
            lambda results: walk(self.tmpdir, validateoutput, None)
            )

    def test_end_flush(self):
        self.tmpdir = mkdtemp()
        chunk_size = 10
        result_sink = ResultSink(self.tmpdir, chunk_size=chunk_size)
        test_data = {'test_method': 'test_end_flush'}
        for _ in xrange(chunk_size + 1):
            result_sink.send(test_data)

        def validateoutput(_, dirname, fnames):
            assert len(fnames) == 2
            for fname in fnames:
                path = join(dirname, fname)
                with open(path, 'r') as testfile:
                    results = json.load(testfile)
                    for result in results:
                        assert 'test_method' in result
                        assert result['test_method'] == 'test_end_flush'
        return result_sink.end_flush().addCallback(
            lambda results: walk(self.tmpdir, validateoutput, None)
            )

    def tearDown(self):
        rmtree(self.tmpdir)
