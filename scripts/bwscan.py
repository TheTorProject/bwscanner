import sys
import time

from bwscanner.attacher import start_tor, setconf_fetch_all_descs
from bwscanner.measurement import BwScan

from twisted.internet import reactor
from twisted.python import log

from txtorcon import build_local_tor_connection, TorConfig

def main():
    log.startLogging(sys.stdout)
    launch_tor = True
    if launch_tor:
        c = TorConfig()
        #FIXME: check these values, parametize!
        c.CircuitBuildTimeout = 20
        c.LearnCircuitBuildTimeout = 0
        c.CircuitIdleTimeout = 20
        c.FetchDirInfoEarly = 1
        c.FetchDirInfoExtraEarly = 1
        c.FetchUselessDescriptors = 1
        tor = start_tor(c)
    else:
        tor = build_local_tor_connection(reactor)
        tor.addCallback(setconf_fetch_all_descs)
    # check that each run is producing the same input set!
    tor.addCallback(BwScan, reactor, './logs', partitions=1, this_partition=0)
    tor.addCallback(lambda scanner: scanner.run_scan())
    tor.addCallback(lambda _: reactor.stop())
    reactor.run()

if __name__ == '__main__':
    main()
