
# this code was copied from Tahoe-LAFS to help with writing unit tests.

from twisted.internet import defer
#from twisted.python import log
import exceptions, os
from repr import Repr

class BetterRepr(Repr):
    def __init__(self):
        Repr.__init__(self)

        # Note: These levels can get adjusted dynamically!  My goal is to get more info when printing important debug stuff like exceptions and stack traces and less info when logging normal events.  --Zooko 2000-10-14
        self.maxlevel = 6
        self.maxdict = 6
        self.maxlist = 6
        self.maxtuple = 6
        self.maxstring = 300
        self.maxother = 300

    def repr_function(self, obj, level):
        if hasattr(obj, 'func_code'):
            return '<' + obj.func_name + '() at ' + os.path.basename(obj.func_code.co_filename) + ':' + str(obj.func_code.co_firstlineno) + '>'
        else:
            return '<' + obj.func_name + '() at (builtin)'

    def repr_instance_method(self, obj, level):
        if hasattr(obj, 'func_code'):
            return '<' + obj.im_class.__name__ + '.' + obj.im_func.__name__ + '() at ' + os.path.basename(obj.im_func.func_code.co_filename) + ':' + str(obj.im_func.func_code.co_firstlineno) + '>'
        else:
            return '<' + obj.im_class.__name__ + '.' + obj.im_func.__name__ + '() at (builtin)'

    def repr_long(self, obj, level):
        s = `obj` # XXX Hope this isn't too slow...
        if len(s) > self.maxlong:
            i = max(0, (self.maxlong-3)/2)
            j = max(0, self.maxlong-3-i)
            s = s[:i] + '...' + s[len(s)-j:]
        if s[-1] == 'L':
            return s[:-1]
        return s

    def repr_instance(self, obj, level):
        """
        If it is an instance of Exception, format it nicely (trying to emulate
        the format that you see when an exception is actually raised, plus
        bracketing '<''s).  If it is an instance of dict call self.repr_dict()
        on it.  If it is an instance of list call self.repr_list() on it. Else
        call Repr.repr_instance().
        """
        if isinstance(obj, exceptions.Exception):
            # Don't cut down exception strings so much.
            tms = self.maxstring
            self.maxstring = max(512, tms * 4)
            tml = self.maxlist
            self.maxlist = max(12, tml * 4)
            try:
                if hasattr(obj, 'args'):
                    if len(obj.args) == 1:
                        return '<' + obj.__class__.__name__ + ': ' + self.repr1(obj.args[0], level-1) + '>'
                    else:
                        return '<' + obj.__class__.__name__ + ': ' + self.repr1(obj.args, level-1) + '>'
                else:
                    return '<' + obj.__class__.__name__ + '>'
            finally:
                self.maxstring = tms
                self.maxlist = tml

        if isinstance(obj, dict):
            return self.repr_dict(obj, level)

        if isinstance(obj, list):
            return self.repr_list(obj, level)

        return Repr.repr_instance(self, obj, level)

    def repr_list(self, obj, level):
        """
        copied from standard repr.py and fixed to work on multithreadedly mutating lists.
        """
        if level <= 0: return '[...]'
        n = len(obj)
        myl = obj[:min(n, self.maxlist)]
        s = ''
        for item in myl:
            entry = self.repr1(item, level-1)
            if s: s = s + ', '
            s = s + entry
        if n > self.maxlist: s = s + ', ...'
        return '[' + s + ']'

    def repr_dict(self, obj, level):
        """
        copied from standard repr.py and fixed to work on multithreadedly mutating dicts.
        """
        if level <= 0: return '{...}'
        s = ''
        n = len(obj)
        items = obj.items()[:min(n, self.maxdict)]
        items.sort()
        for key, val in items:
            entry = self.repr1(key, level-1) + ':' + self.repr1(val, level-1)
            if s: s = s + ', '
            s = s + entry
        if n > self.maxdict: s = s + ', ...'
        return '{' + s + '}'

# This object can be changed by other code updating this module's "brepr"
# variables.  This is so that (a) code can use humanreadable with
# "from humanreadable import hr; hr(mything)", and (b) code can override
# humanreadable to provide application-specific human readable output
# (e.g. libbase32's base32id.AbbrevRepr).
brepr = BetterRepr()

def hr(x):
    return brepr.repr(x)

def _assert(___cond=False, *___args, **___kwargs):
    if ___cond:
        return True
    msgbuf=[]
    if ___args:
        msgbuf.append("%s %s" % tuple(map(hr, (___args[0], type(___args[0]),))))
        msgbuf.extend([", %s %s" % tuple(map(hr, (arg, type(arg),))) for arg in ___args[1:]])
        if ___kwargs:
            msgbuf.append(", %s: %s %s" % ((___kwargs.items()[0][0],) + tuple(map(hr, (___kwargs.items()[0][1], type(___kwargs.items()[0][1]),)))))
    else:
        if ___kwargs:
            msgbuf.append("%s: %s %s" % ((___kwargs.items()[0][0],) + tuple(map(hr, (___kwargs.items()[0][1], type(___kwargs.items()[0][1]),)))))
    msgbuf.extend([", %s: %s %s" % tuple(map(hr, (k, v, type(v),))) for k, v in ___kwargs.items()[1:]])

    raise AssertionError, "".join(msgbuf)

def _with_log(op, res):
    """
    The default behaviour on firing an already-fired Deferred is unhelpful for
    debugging, because the AlreadyCalledError can easily get lost or be raised
    in a context that results in a different error. So make sure it is logged
    (for the abstractions defined here). If we are in a test, log.err will cause
    the test to fail.
    """
    try:
        op(res)
    except defer.AlreadyCalledError, e:
        print "err %r" % (repr(op),)

class HookMixin:
    """
    I am a helper mixin that maintains a collection of named hooks, primarily
    for use in tests. Each hook is set to an unfired Deferred using 'set_hook',
    and can then be fired exactly once at the appropriate time by '_call_hook'.
    If 'ignore_count' is given, that number of calls to '_call_hook' will be
    ignored before firing the hook.

    I assume a '_hooks' attribute that should set by the class constructor to
    a dict mapping each valid hook name to None.
    """
    def set_hook(self, name, d=None, ignore_count=0):
        """
        Called by the hook observer (e.g. by a test).
        If d is not given, an unfired Deferred is created and returned.
        The hook must not already be set.
        """
        self._log("set_hook %r, ignore_count=%r" % (name, ignore_count))
        if d is None:
            d = defer.Deferred()
        _assert(ignore_count >= 0, ignore_count=ignore_count)
        _assert(name in self._hooks, name=name)
        _assert(self._hooks[name] is None, name=name, hook=self._hooks[name])
        _assert(isinstance(d, defer.Deferred), d=d)

        self._hooks[name] = (d, ignore_count)
        return d

    def _call_hook(self, res, name):
        """
        Called to trigger the hook, with argument 'res'. This is a no-op if
        the hook is unset. If the hook's ignore_count is positive, it will be
        decremented; if it was already zero, the hook will be unset, and then
        its Deferred will be fired synchronously.

        The expected usage is "deferred.addBoth(self._call_hook, 'hookname')".
        This ensures that if 'res' is a failure, the hook will be errbacked,
        which will typically cause the test to also fail.
        'res' is returned so that the current result or failure will be passed
        through.
        """
        hook = self._hooks[name]
        if hook is None:
            return None

        (d, ignore_count) = hook
        self._log("call_hook %r, ignore_count=%r" % (name, ignore_count))
        if ignore_count > 0:
            self._hooks[name] = (d, ignore_count - 1)
        else:
            self._hooks[name] = None
            _with_log(d.callback, res)
        return res

    def _log(self, msg):
        print msg

