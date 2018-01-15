'''
IPython Twisted
===============
Run a Twisted reactor inside IPython. Works with newer IPython versions (tested with 0.13.2).
Logging is automatically enabled via `logging.basicConfig(level=logging.DEBUG)`.

__url__ = "https://gist.github.com/kived/8721434"

This file is distributed under the following license:

Copyright (c) 2015- Ryan Pessa



Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:



The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.



THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
'''

__author__ = "Ryan Pessa <dkived@gmail.com>"


import logging
from twisted.internet import defer

logging.basicConfig(level=logging.DEBUG)


def __install():
    log = logging.getLogger('tpython')
    log.info('setting up twisted reactor in ipython loop')

    from twisted.internet import _threadedselect
    _threadedselect.install()

    from twisted.internet import reactor
    from collections import deque
    from IPython.lib import inputhook
    from IPython import InteractiveShell

    q = deque()

    def reactor_wake(twisted_loop_next, q=q):
        q.append(twisted_loop_next)

    def reactor_work(*_args):
        if q:
            while len(q):
                q.popleft()()
        return 0

    def reactor_start(*_args):
        log.info('starting twisted reactor in ipython')
        reactor.interleave(reactor_wake)  # @UndefinedVariable
        inputhook.set_inputhook(reactor_work)

    def reactor_stop():
        if reactor.threadpool:  # @UndefinedVariable
            log.info('stopping twisted threads')
            reactor.threadpool.stop()  # @UndefinedVariable
        log.info('shutting down twisted reactor')
        reactor._mainLoopShutdown()  # @UndefinedVariable

    ip = InteractiveShell.instance()

    ask_exit = ip.ask_exit

    def ipython_exit():
        reactor_stop()
        return ask_exit()

    ip.ask_exit = ipython_exit

    reactor_start()

    return reactor


reactor = __install()

from txtorcon import build_local_tor_connection
build_local_tor_connection(reactor).addCallback(
    lambda tor: globals().update(tor=tor))
