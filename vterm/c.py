from ._c import ffi
from ._c.lib import *

def _init():
    g = globals()
    for t in ffi.list_types()[0]:
        g[t] = ffi.typeof(t)
    from .cb_except import restore_exception
    for n, f in g.items():
        if callable(f):
            g[n] = restore_exception(f)
_init()
del _init

def VTERM_KEY_FUNCTION(n):
    return VTERM_KEY_FUNCTION_0 + n
def vterm_pos_cmp(a, b):
    if a.row == b.row:
        return a.col - b.col
    else:
        return a.row - b.row
def vterm_rect_contains(r, p):
    return (r.start_row <= p.row < r.end_row
            and r.start_col <= p.col < r.end_col)
def vterm_rect_move(rect, row_delta, col_delta):
    rect.start_row += row_delta
    rect.end_row += row_delta
    rect.start_col += col_delta
    rect.end_col += col_delta
CSI_ARG_FLAG_MORE = 1<<31
CSI_ARG_MASK      = ~CSI_ARG_FLAG_MORE
def CSI_ARG_HAS_MORE(a):
    return a & CSI_ARG_FLAG_MORE
def CSI_ARG(a):
    return a & CSI_ARG_MASK
CSI_ARG_MISSING = (1<<31)-1
def CSI_ARG_IS_MISSING(a):
    return CSI_ARG(a) == CSI_ARG_MISSING
def CSI_ARG_OR(a, default):
    if CSI_ARG(a) == CSI_ARG_MISSING:
        return default
    else:
        return CSI_ARG(a)
def CSI_ARG_COUNT(a):
    if CSI_ARG(a) == CSI_ARG_MISSING or CSI_ARG(a) == 0:
        return 1
    else:
        return CSI_ARG(a)
VTERM_MAX_CHARS_PER_CELL = 6
