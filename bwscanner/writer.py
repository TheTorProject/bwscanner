import datetime
import os.path
import json

from twisted.internet import threads, defer

from bwscanner.logger import log


class ResultSink(object):
    """
    Send results to this sink, they'll eventually be written
    via another thread so as to not block the reactor.
    """

    def __init__(self, out_dir, chunk_size=1000):
        """
        out_dir: the directory to json log files to
        chunk_size: the max amount of data to write per file
        """
        self.out_dir = out_dir
        self.chunk_size = chunk_size
        self.buffer = []
        self.writing = False
        self.current_task = defer.succeed(None)

    def send(self, res):
        """
        send returns a deferred which represents our current deferred work chain.
        No tasks are appended to our deferred chain unless the size of res matches or exceeds
        the chunk boundary.
        """
        self.buffer.append(res)

        def write():
            wf = open(log_path, "w")
            try:
                json.dump(chunk, wf, sort_keys=True)
            finally:
                wf.close()

        # buffer is full, write to disk
        while len(self.buffer) >= int(self.chunk_size):
            chunk = self.buffer[:self.chunk_size]
            self.buffer = self.buffer[self.chunk_size:]
            log_path = os.path.join(self.out_dir,
                                    "%s-scan.json" % (datetime.datetime.utcnow().isoformat()))

            self.current_task.addCallback(lambda ign: threads.deferToThread(write))

        # buffer is not full, return deferred for current batch
        return self.current_task

    def end_flush(self):
        """
        Return the current deferred work chain.
        This last write is not performed in separate thread.
        """
        def flush():
            log_path = os.path.join(self.out_dir,
                                    "%s-scan.json" % (datetime.datetime.utcnow().isoformat()))
            wf = open(log_path, "w")
            try:
                json.dump(self.buffer, wf, sort_keys=True)
            finally:
                wf.close()
            log.info("Finished writing measurement values to {log_path}.", log_path=log_path)

        def maybe_do_work(result):
            if len(self.buffer) != 0:
                flush()
            return None

        return self.current_task.addCallback(maybe_do_work)
