import datetime
import os.path
import json

from twisted.internet import threads, defer


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

        self.buffer.append(res)
        # buffer is full, write to disk
        if len(self.buffer) >= self.chunk_size:
            chunk = self.buffer[:self.chunk_size]
            self.buffer = self.buffer[self.chunk_size:]
            log_path = os.path.join(self.out_dir,
                                    "%s-scan.json" % (datetime.datetime.utcnow().isoformat()))

            def write():
                wf = open(log_path, "w")
                try:
                    json.dump(chunk, wf, sort_keys=True)
                finally:
                    wf.close()
            self.current_task.addCallback(lambda ign: threads.deferToThread(write))
            return self.current_task

        # buffer is not full, return deferred for current batch
        return self.current_task

    def end_flush(self):
        """
        Write buffered contents to disk.
        There's no need to perform this write
        in a seperate thread.
        """
        def flush():
            if len(self.buffer) == 0:
                return None
            log_path = os.path.join(self.out_dir,
                                    "%s-scan.json" % (datetime.datetime.utcnow().isoformat()))
            wf = open(log_path, "w")
            try:
                json.dump(self.buffer, wf, sort_keys=True)
            finally:
                wf.close()
            return None
        return threads.deferToThread(flush)
