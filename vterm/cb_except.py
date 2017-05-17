import functools
import threading


_thread_locals = threading.local()


# Install this *before* ffi.def_extern, around all callbacks.
def onerror(ty, v, tb):
    _thread_locals.exception = v
    return None


# Install this around all c lib functions.
def restore_exception(fn):
    @functools.wraps(fn)
    def restorer(*args, **kwargs):
        if getattr(_thread_locals, 'exception', Ellipsis) is Ellipsis:
            _thread_locals.exception = None
        rv = fn(*args, **kwargs)
        e = _thread_locals.exception
        if e is not None:
            _thread_locals.exception = None
            raise e
        return rv
    return restorer
