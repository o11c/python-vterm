import functools
import threading


_thread_locals = threading.local()


# Install this *before* ffi.def_extern, around all callbacks.
def save_exception(fn):
    @functools.wraps(fn)
    def saver(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except BaseException as e:
            _thread_locals.exception = e
            return None
    return saver


# Install this around all c lib functions.
def restore_exception(fn):
    @functools.wraps(fn)
    def restorer(*args, **kwargs):
        assert getattr(_thread_locals, 'exception', None) is None
        _thread_locals.exception = None
        rv = fn(*args, **kwargs)
        e = _thread_locals.exception
        if e is not None:
            _thread_locals.exception = None
            raise e
        return rv
    return restorer
