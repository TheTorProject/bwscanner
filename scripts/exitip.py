import datetime
import json
import re
import sys
from bwscanner.attacher import SOCKSClientStreamAttacher, start_tor
from bwscanner.circuit import ExitScan
from bwscanner.fetcher import OnionRoutedAgent
from twisted.internet import defer, reactor, task
from twisted.python import log
from twisted.web.client import readBody
from twisted.web._newclient import ResponseNeverReceived, ResponseFailed
from txsocksx.errors import HostUnreachable, TTLExpired
from txtorcon import TorConfig

def fetch(path, url, state):
    agent = OnionRoutedAgent(reactor, path=path, state=state)
    request = agent.request("GET", url)
    reactor.callLater(10, request.cancel)
    request.addCallback(readBody)

    def parse_ip(body):
        exit_ip = path[-1].ip
        try:
            checked_ip = re.search("<strong>(.*)</strong>", body).group(1)
            return exit_ip, checked_ip
        except AttributeError:
            return exit_ip, None

    request.addCallback(parse_ip)
    def err(failure):
        failure.trap(defer.CancelledError, ResponseNeverReceived,
                     ResponseFailed, HostUnreachable, TTLExpired)
        log.err(failure)
    request.addErrback(err)
    return request

def run_scan(state):
    circuits = ExitScan(state)
    url = 'https://check.torproject.org'
    outfile = open("exit-addresses.%s.json" % datetime.datetime.utcnow().isoformat(), 'w+')
    all_tasks_done = defer.Deferred()
    tasks = []
    def pop(circuits):
        try:
            tasks.append(task.deferLater(
                reactor, 0, fetch, circuits.next(), url, state))
            reactor.callLater(.2, pop, circuits)
        except StopIteration:
            results = defer.DeferredList(tasks)
            results.addCallback(save_results, outfile)\
                   .addCallback(lambda _: outfile.close)\
                   .chainDeferred(all_tasks_done)

    reactor.callLater(0, pop, circuits)
    return all_tasks_done

def shutdown(ignore):
    reactor.stop()

def add_attacher(state):
    state.set_attacher(SOCKSClientStreamAttacher(state), reactor)
    return state

def setup_failed(failure):
    log.err(failure)

def save_results(result, outfile):
    outfile.write(json.dumps(dict([r[1] for r in result if r[1] != None])))

def main():
    log.startLogging(sys.stdout)
    tor = start_tor(TorConfig())
    tor.addCallback(add_attacher)
    tor.addCallback(run_scan)
    tor.addErrback(log.err)
    tor.addBoth(shutdown)
    reactor.run()

if __name__ == '__main__':
    main()
