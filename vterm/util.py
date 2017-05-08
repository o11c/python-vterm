# Always use the backport because there's no knowing how the stdlib is broken today.
from .backports.enum import Enum, Flag
import functools
import types


def make_enum(mod, name, search_mod, search_prefix, *, cls=Enum, extra=[], exclude=lambda k: False):
    assert isinstance(mod, str)
    assert isinstance(search_mod, types.ModuleType)
    l = len(search_prefix)
    names = []
    for k, v in vars(search_mod).items():
        if k.startswith(search_prefix) and not exclude(k):
            names.append((k[l:], v))
    names.extend(extra)
    names.sort(key=lambda kv: (kv[1], kv[0]))
    return cls(name, names, module=mod)


make_flags = functools.partial(make_enum, cls=Flag)
