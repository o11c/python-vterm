import collections
import weakref

import attr

from . import c, cb_except, util


def _read_str_exact(ctp, len_):
    # No point in using c.ffi.unpack(ctp, len_), since there's no char32_t support.
    if False and len_ and ctp[0] == 0xFFffFFff:
        return ''
    return ''.join([chr(ctp[i]) for i in range(len_)])
def _read_str(ctp, *, max_len=float('inf')):
    # Can't use c.ffi.string(), since there's no char32_t support.
    if max_len and ctp[0] == 0xFFffFFff:
        return ''
    rv = []
    i = 0
    while i < max_len and ctp[i]:
        rv.append(chr(ctp[i]))
        i += 1
    return ''.join(rv)


@attr.s(slots=True, frozen=True)
class Size:
    rows = attr.ib()
    cols = attr.ib()
STANDARD_SIZE = Size(cols=80, rows=25)


Modifier = util.make_flags(__name__, 'Modifier', c, 'VTERM_MOD_')
Modifier.c_type = 'VTermModifier*'
Modifier.fields = None


Key = util.make_enum(__name__, 'Key', c, 'VTERM_KEY_', extra=[('FUNCTION_%d' % i, c.VTERM_KEY_FUNCTION(i)) for i in range(1, 256)], exclude=lambda k: k == 'VTERM_KEY_FUNCTION')
def FUNCTION(n):
    assert 0 <= n < 255
    return Key(c.VTERM_KEY_FUNCTION(n))
FUNCTION.__qualname__ = 'Key.FUNCTION'
Key.FUNCTION = FUNCTION
del FUNCTION
Key.c_type = 'VTermKey*'
Key.fields = None


@attr.s(slots=True)
class _KeepAlive:
    parser_callbacks = attr.ib(default=None, init=False)
    state_callbacks = attr.ib(default=None, init=False)
    state_parser_fallbacks = attr.ib(default=None, init=False)
    screen_callbacks = attr.ib(default=None, init=False)


class VTerm:
    __slots__ = ('_keep_alive', '_vt', '_state', '_screen')
    def __init__(self, size=STANDARD_SIZE):
        self._keep_alive = _KeepAlive()
        gc = c.ffi.gc
        dtor = c.vterm_free
        self._vt = gc(c.vterm_new(size.rows, size.cols), dtor)
        self._state = c.vterm_obtain_state(self._vt)
        self._screen = c.vterm_obtain_screen(self._vt)

        self.set_utf8(True)
        self.reset(True)

    def __repr__(self):
        size = self.get_size()
        output = c.vterm_output_get_buffer_current(self._vt)
        return '<%s size=%r output=%d>' % (type(self).__name__, size, output)

    def get_size(self):
        rowsp = c.ffi.new('int*')
        colsp = c.ffi.new('int*')
        c.vterm_get_size(self._vt, rowsp, colsp)
        return Size(rows=rowsp[0], cols=colsp[0])

    def set_size(self, size):
        c.vterm_set_size(self._vt, size.rows, size.cols)

    def get_utf8(self):
        return c.vterm_get_utf8(self._vt)

    def set_utf8(self, is_utf8):
        return c.vterm_set_utf8(self._vt, is_utf8)

    def input_write(self, bytes_):
        len_ = len(bytes_)
        return c.vterm_input_write(self._vt, bytes_, len_)

    def output_read(self):
        len_ = c.vterm_output_get_buffer_current(self._vt)
        if len_ == 0:
            return b''
        buf = c.ffi.new('char[]', len_)
        rv = c.vterm_output_read(self._vt, buf, len_)
        return c.ffi.unpack(buf, rv)

    def keyboard_unichar(self, cp, mod):
        c.vterm_keyboard_unichar(self._vt, cp, to_native(mod, cls=Modifier))

    def keyboard_key(self, key, mod):
        c.vterm_keyboard_key(self._vt, key.value, to_native(mod, cls=Modifier))

    def keyboard_start_paste(self):
        c.vterm_keyboard_start_paste(self._vt)

    def keyboard_end_paste(self):
        c.vterm_keyboard_end_paste(self._vt)

    def mouse_move(self, pos, mod):
        c.vterm_mouse_move(self._vt, pos.row, pos.col, to_native(mod, cls=Modifier))

    def mouse_button(self, button, pressed, mod):
        c.vterm_mouse_button(self._vt, button, pressed, to_native(mod, cls=Modifier))

    def _parser_set_callbacks(self, callbacks):
        # Normally we use the VTermState, which installs its own instead!
        user = self._keep_alive.parser_callbacks = c.ffi.new_handle(callbacks)
        c.vterm_parser_set_callbacks(self._vt, _g_parser_callbacks, user)


    def _state_set_callbacks(self, callbacks):
        user = self._keep_alive.state_callbacks = c.ffi.new_handle(callbacks)
        c.vterm_state_set_callbacks(self._state, _g_state_callbacks, user)

    def state_set_unrecognised_fallbacks(self, fallbacks):
        user = self._keep_alive.state_parser_fallbacks = c.ffi.new_handle(fallbacks)
        c.vterm_state_set_unrecognised_fallbacks(self._state, _g_parser_callbacks, user)

    def state_reset(self, hard):
        c.vterm_state_reset(self._state, hard)

    def state_get_cursorpos(self):
        pos = c.ffi.new('VTermPos*')
        c.vterm_state_get_cursorpos(self._state, pos)
        return from_native(pos, cls=Pos)

    def state_get_default_colors(self):
        fg = c.ffi.new('VTermColor*')
        bg = c.ffi.new('VTermColor*')
        c.vterm_state_get_default_colors(self._state, fg, bg)
        rv_fg = from_native(fg, cls=Color)
        rv_bg = from_native(fg, cls=Color)
        return (rv_fg, rv_bg)

    def state_get_palette_color(self, idx):
        col = c.ffi.new('VTermColor*')
        c.vterm_state_get_palette_color(self._state, idx, col)
        return from_native(col, cls=Color)

    def state_set_default_colors(self, fg, bg):
        fg = to_native(fg, cls=Color)
        bg = to_native(bg, cls=Color)
        c.vterm_state_set_default_colors(self._state, c_fg, c_bg)

    def state_set_palette_color(self, idx, col):
        col = to_native(col, cls=Color)
        c.vterm_state_set_palette_color(self._state, idx, c_col)

    def state_set_bold_highbright(self, bold_is_highbright):
        c.vterm_state_set_bold_highbright(self._state, bold_is_highbright)

    def state_get_penattr(self, attr):
        c_attr = to_native(attr, cls=Attr)
        val = c.ffi.new('VTermValue*')
        if c.vterm_state_get_penattr(self._state, c_attr, val):
            return from_native(val, attr=attr)
        raise LookupError(attr)

    def state_set_termprop(self, prop, val):
        val = to_native(val, prop=prop)
        if not c.vterm_state_set_termprop(self._state, prop, val):
            raise LookupError(prop)

    def state_get_lineinfo(self, row):
        rv = c.vterm_state_get_lineinfo(self._state, row)
        return from_native(rv, cls=LineInfo)


    def screen_set_callbacks(self, callbacks):
        user = self._keep_alive.screen_callbacks = c.ffi.new_handle(callbacks)
        c.vterm_screen_set_callbacks(self._screen, _g_screen_callbacks, user)

    def screen_set_unrecognised_fallbacks(self, fallbacks):
        user = self._keep_alive.screen_parser_fallbacks = c.ffi.new_handle(fallbacks)
        c.vterm_screen_set_unrecognised_fallbacks(self._screen, _g_parser_callbacks, user)

    def screen_enable_altscreen(self, altscreen):
        c.vterm_screen_enable_altscreen(self._screen, altscreen)

    def screen_flush_damage(self):
        c.vterm_screen_flush_damage(self._screen)

    def screen_set_damage_merge(self, size):
        c.vterm_screen_set_damage_merge(self._screen, to_native(size, cls=DamageSize))

    def screen_reset(self, hard):
        c.vterm_screen_reset(self._screen, hard)

    def screen_get_chars(self, rect):
        rect = to_native(rect, cls=Rect)
        l = c.vterm_screen_get_chars(self._screen, c.ffi.NULL, 0, rect[0])
        buf = c.ffi.new('uint32_t[]', l)
        c.vterm_screen_get_chars(self._screen, buf, l, rect[0])
        return _read_str_exact(buf, l)

    def screen_get_text(self, rect):
        rect = to_native(rect, cls=Rect)
        l = c.vterm_screen_get_text(self._screen, c.ffi.NULL, 0, rect[0])
        buf = c.ffi.new('char[]', l)
        c.vterm_screen_get_text(self._screen, buf, l, rect[0])
        return c.ffi.unpack(buf, l)

    def screen_get_attrs_extent(self, pos, attrs, *, colspan=(0, -1)):
        rv = c.ffi.new('VTermRect*')
        rv.start_col, rv.end_col = colspan
        pos = to_native(pos, cls=Pos)
        attrs = to_native(attrs, cls=AttrMask)
        c.vterm_screen_get_attrs_extent(self._screen, rv, pos[0], attrs)
        return from_native(rv, cls=Rect)

    def screen_get_cell(self, pos):
        rv = c.ffi.new('VTermScreenCell*')
        pos = to_native(pos, cls=Pos)
        c.vterm_screen_get_cell(self._screen, pos[0], rv)
        return from_native(rv, cls=ScreenCell)

    def screen_is_eol(self, pos):
        pos = to_native(pos, cls=Pos)
        return c.vterm_screen_is_eol(self._screen, pos[0])
for k in sorted(dir(VTerm)):
    if k in ('state_set_unrecognised_fallbacks', 'state_reset'):
        # screen-level functions do extra work, then call the state-level one.
        continue
    for p in ('state_', 'screen_'):
        if k.startswith(p):
            v = getattr(VTerm, k)
            k2 = k[len(p):]
            if getattr(VTerm, k2, None) in (None, v):
                setattr(VTerm, k2, v)
            else:
                raise KeyError('cross duplicate %r vs %r' % (k, k2))
            break
del k, p, v, k2


@attr.s(slots=True, frozen=True)
class Pos:
    row = attr.ib()
    col = attr.ib()
Pos.c_type = 'VTermPos*'
Pos.fields = ['row', 'col']


@attr.s(slots=True, frozen=True)
class Rect:
    start_row = attr.ib()
    end_row = attr.ib()
    start_col = attr.ib()
    end_col = attr.ib()

    def __contains__(self, pos):
        if not isinstance(pos, Pos):
            raise TypeError('Expected \'Pos\' instance, not %r' % type(pos).__name__)
        return c.vterm_rect_contains(self, pos)

Rect.c_type = 'VTermRect*'
Rect.fields = ['start_row', 'end_row', 'start_col', 'end_col']


@attr.s(slots=True, frozen=True, repr=False)
class Color:
    red = attr.ib()
    green = attr.ib()
    blue = attr.ib()

    def __repr__(self):
        return '#%02x%02x%02x' % (self.red, self.green, self.blue)
Color.c_type = 'VTermColor*'
Color.fields = ['red', 'green', 'blue']


ValueType = util.make_enum(__name__, 'ValueType', c, 'VTERM_VALUETYPE_')
ValueType.c_type = 'VTermValueType*'
ValueType.fields = None


Attr = util.make_enum(__name__, 'Attr', c, 'VTERM_ATTR_', exclude=lambda k: k.endswith('_MASK'))
Attr.c_type = 'VTermAttr*'
Attr.fields = None


Prop = util.make_enum(__name__, 'Prop', c, 'VTERM_PROP_', exclude=lambda k: k.startswith(('VTERM_PROP_CURSORSHAPE_', 'VTERM_PROP_MOUSE_')))
Prop.c_type = 'VTermProp*'
Prop.fields = None


PropCursorShape = util.make_enum(__name__, 'PropCursorShape', c, 'VTERM_PROP_CURSORSHAPE_')
PropCursorShape.c_type = 'int*'
PropCursorShape.fields = None


PropMouse = util.make_enum(__name__, 'PropMouse', c, 'VTERM_PROP_MOUSE_')
PropMouse.c_type = 'int*'
PropMouse.fields = None


@attr.s(slots=True, frozen=True)
class GlyphInfo:
    chars = attr.ib(convert=_read_str) # instances always come *from* C, not vice versa
    width = attr.ib()
    protected_cell = attr.ib()
    dwl = attr.ib()
    dhl = attr.ib()
GlyphInfo.c_type = 'VTermGlyphInfo*'
GlyphInfo.fields = ['chars', 'width', 'protected_cell', 'dwl', 'dhl']


@attr.s(slots=True, frozen=True)
class LineInfo:
    doublewidth = attr.ib()
    doubleheight = attr.ib()
LineInfo.c_type = 'VTermLineInfo*'
LineInfo.fields = ['doublewidth', 'doubleheight']


@attr.s(slots=True, frozen=True)
class ScreenCell:
    # for sb_pushline/sb_popline, store the raw line arrays.
    # thus, instances always come *from* C, not vice versa
    chars = attr.ib(convert=lambda chs: _read_str(chs, max_len=6))
    width = attr.ib(convert=lambda b: b[0])
    attrs = attr.ib(convert=lambda ats: from_native(ats, cls=ScreenCell.Attrs))
    fg = attr.ib(convert=lambda clr: from_native(clr, cls=Color))
    bg = attr.ib(convert=fg.convert)

    @attr.s(slots=True, frozen=True, repr=False)
    class Attrs:
        bold = attr.ib()
        underline = attr.ib()
        italic = attr.ib()
        blink = attr.ib()
        reverse = attr.ib()
        strike = attr.ib()
        font = attr.ib()
        dwl = attr.ib()
        dhl = attr.ib()

        def __repr__(self):
            bits = []
            bits.append('<')
            bits.append(type(self).__qualname__)
            default = True
            for a in self.__attrs_attrs__:
                v = getattr(self, a.name)
                if v:
                    default = False
                    bits.append(' %s=%s' % (a.name, v))
            if default:
                bits.append(' default')
            bits.append('>')
            return ''.join(bits)
ScreenCell.c_type = 'VTermScreenCell*'
ScreenCell.fields = ['chars', 'width', 'attrs', 'fg', 'bg']
ScreenCell.Attrs.c_type = None
ScreenCell.Attrs.fields = ['bold', 'underline', 'italic', 'blink', 'reverse', 'strike', 'font', 'dwl', 'dhl']


DamageSize = util.make_enum(__name__, 'DamageSize', c, 'VTERM_DAMAGE_')
DamageSize.c_type = 'VTermDamageSize*'
DamageSize.fields = None


AttrMask = util.make_flags(__name__, 'AttrMask', c, 'VTERM_ATTR_', exclude=lambda k: not k.endswith('_MASK'))
AttrMask.c_type = 'VTermAttrMask*'
AttrMask.fields = None


class AbstractCallbacks:
    def __init__(self, vt):
        self._vt = weakref.ref(vt)

    @property
    def vt(self):
        # Break reference cycle
        rv = (self._vt)()
        assert rv is not None
        return rv

class ParserCallbacks(AbstractCallbacks):
    def text(self, bytes_):
        return 0
    def control(self, control):
        return 0
    def escape(self, bytes_):
        return 0
    def csi(self, leader, args, intermed, command):
        return 0
    def osc(self, command):
        return 0
    def dcs(self, command):
        return 0
    def resize(self, size):
        return 0

@c.ffi.def_extern(onerror=cb_except.onerror)
def cb_parser_text(bytes_, len_, user):
    callbacks = c.ffi.from_handle(user)
    return callbacks.text(c.ffi.unpack(bytes_, len_))
@c.ffi.def_extern(onerror=cb_except.onerror)
def cb_parser_control(control, user):
    callbacks = c.ffi.from_handle(user)
    return callbacks.control(control)
@c.ffi.def_extern(onerror=cb_except.onerror)
def cb_parser_escape(bytes_, len_, user):
    callbacks = c.ffi.from_handle(user)
    return callbacks.escape(c.ffi.unpack(bytes_, len_))
@c.ffi.def_extern(onerror=cb_except.onerror)
def cb_parser_csi(leader, args, argcount, intermed, command, user):
    callbacks = c.ffi.from_handle(user)
    args2 = [None] * argcount
    # No point in using c.ffi.unpack(), since we're munging anyway.
    for i in range(argcount):
        a = args[i] % (1 << 32)
        colon = bool(a & c.CSI_ARG_FLAG_MORE)
        a &= c.CSI_ARG_MASK
        if a == c.CSI_ARG_MISSING:
            a = None
        args2[i] = (a, colon)
    leader = None if leader == c.ffi.NULL else c.ffi.string(leader)
    intermed = None if intermed == c.ffi.NULL else c.ffi.string(intermed)
    return callbacks.csi(leader, args2, intermed, command)
@c.ffi.def_extern(onerror=cb_except.onerror)
def cb_parser_osc(command, cmdlen, user):
    callbacks = c.ffi.from_handle(user)
    return callbacks.osc(c.ffi.unpack(command, cmdlen))
@c.ffi.def_extern(onerror=cb_except.onerror)
def cb_parser_dcs(command, cmdlen, user):
    callbacks = c.ffi.from_handle(user)
    return callbacks.dcs(c.ffi.unpack(command, cmdlen))
@c.ffi.def_extern(onerror=cb_except.onerror)
def cb_parser_resize(rows, cols, user):
    callbacks = c.ffi.from_handle(user)
    return callbacks.resize(Size(rows=rows, cols=cols))

_g_parser_callbacks = c.ffi.new('VTermParserCallbacks*')
_g_parser_callbacks.text = c.cb_parser_text.__wrapped__
_g_parser_callbacks.control = c.cb_parser_control.__wrapped__
_g_parser_callbacks.escape = c.cb_parser_escape.__wrapped__
_g_parser_callbacks.csi = c.cb_parser_csi.__wrapped__
_g_parser_callbacks.osc = c.cb_parser_osc.__wrapped__
_g_parser_callbacks.dcs = c.cb_parser_dcs.__wrapped__
_g_parser_callbacks.resize = c.cb_parser_resize.__wrapped__

class StateCallbacks(AbstractCallbacks):
    def putglyph(self, info, pos):
        return 0
    def movecursor(self, pos, oldpos, visible):
        return 0
    def scrollrect(self, rect, downward, rightward):
        return 0
    def moverect(self, dest, src):
        return 0
    def erase(self, rect, selective):
        return 0
    def initpen(self):
        return 0
    def setpenattr(self, attr, val):
        return 0
    def settermprop(self, prop, val):
        return 0
    def bell(self):
        return 0
    def resize(self, size, delta):
        return 0
    def setlineinfo(self, row, newinfo, oldinfo):
        return 0


@c.ffi.def_extern(onerror=cb_except.onerror)
def cb_state_putglyph(info, pos, user):
    callbacks = c.ffi.from_handle(user)
    info = from_native(info, cls=GlyphInfo)
    pos = from_native(pos, cls=Pos)
    return callbacks.putglyph(info, pos)
@c.ffi.def_extern(onerror=cb_except.onerror)
def cb_state_movecursor(pos, oldpos, visible, user):
    callbacks = c.ffi.from_handle(user)
    pos = from_native(pos, cls=Pos)
    oldpos = from_native(oldpos, cls=Pos)
    return callbacks.movecursor(pos, oldpos, visible)
@c.ffi.def_extern(onerror=cb_except.onerror)
def cb_state_scrollrect(rect, downward, rightward, user):
    callbacks = c.ffi.from_handle(user)
    rect = from_native(rect, cls=Rect)
    return callbacks.scrollrect(rect, downward, rightward)
@c.ffi.def_extern(onerror=cb_except.onerror)
def cb_state_moverect(dest, src, user):
    callbacks = c.ffi.from_handle(user)
    dest = from_native(dest, cls=Rect)
    src = from_native(src, cls=Rect)
    return callbacks.moverect(dest, src)
@c.ffi.def_extern(onerror=cb_except.onerror)
def cb_state_erase(rect, selective, user):
    callbacks = c.ffi.from_handle(user)
    rect = from_native(rect, cls=Rect)
    return callbacks.erase(rect, selective)
@c.ffi.def_extern(onerror=cb_except.onerror)
def cb_state_initpen(user):
    callbacks = c.ffi.from_handle(user)
    return callbacks.initpen()
@c.ffi.def_extern(onerror=cb_except.onerror)
def cb_state_setpenattr(attr, val, user):
    callbacks = c.ffi.from_handle(user)
    attr = from_native(attr, cls=Attr)
    val = from_native(val, attr=attr)
    return callbacks.setpenattr(attr, val)
@c.ffi.def_extern(onerror=cb_except.onerror)
def cb_state_settermprop(prop, val, user):
    callbacks = c.ffi.from_handle(user)
    prop = from_native(prop, cls=Prop)
    val = from_native(val, prop=prop)
    return callbacks.settermprop(prop, val)
@c.ffi.def_extern(onerror=cb_except.onerror)
def cb_state_bell(user):
    callbacks = c.ffi.from_handle(user)
    return callbacks.bell()
@c.ffi.def_extern(onerror=cb_except.onerror)
def cb_state_resize(rows, cols, delta, user):
    callbacks = c.ffi.from_handle(user)
    # TODO - passing the native object
    return callbacks.resize(Size(rows=rows, cols=cols), delta)
@c.ffi.def_extern(onerror=cb_except.onerror)
def cb_state_setlineinfo(row, newinfo, oldinfo, user):
    callbacks = c.ffi.from_handle(user)
    newinfo = from_native(newinfo, cls=LineInfo)
    oldinfo = from_native(oldinfo, cls=LineInfo)
    return callbacks.setlineinfo(row, newinfo, oldinfo)

_g_state_callbacks = c.ffi.new('VTermStateCallbacks*')
_g_state_callbacks.putglyph = c.cb_state_putglyph.__wrapped__
_g_state_callbacks.movecursor = c.cb_state_movecursor.__wrapped__
_g_state_callbacks.scrollrect = c.cb_state_scrollrect.__wrapped__
_g_state_callbacks.moverect = c.cb_state_moverect.__wrapped__
_g_state_callbacks.erase = c.cb_state_erase.__wrapped__
_g_state_callbacks.initpen = c.cb_state_initpen.__wrapped__
_g_state_callbacks.setpenattr = c.cb_state_setpenattr.__wrapped__
_g_state_callbacks.settermprop = c.cb_state_settermprop.__wrapped__
_g_state_callbacks.bell = c.cb_state_bell.__wrapped__
_g_state_callbacks.resize = c.cb_state_resize.__wrapped__
_g_state_callbacks.setlineinfo = c.cb_state_setlineinfo.__wrapped__


class ScreenCallbacks(AbstractCallbacks):
    def damage(self, rect):
        return 0
    def moverect(self, dest, src):
        return 0
    def movecursor(self, pos, oldpos, visible):
        return 0
    def settermprop(self, prop, val):
        return 0
    def bell(self):
        return 0
    def resize(self, size):
        return 0
    def sb_pushline(self, cells):
        return 0
    def sb_popline(self, cells_mut):
        return 0

@c.ffi.def_extern(onerror=cb_except.onerror)
def cb_screen_damage(rect, user):
    callbacks = c.ffi.from_handle(user)
    rect = from_native(rect, cls=Rect)
    return callbacks.damage(rect)
@c.ffi.def_extern(onerror=cb_except.onerror)
def cb_screen_moverect(dest, src, user):
    callbacks = c.ffi.from_handle(user)
    dest = from_native(dest, cls=Rect)
    src = from_native(src, cls=Rect)
    return callbacks.moverect(dest, src)
@c.ffi.def_extern(onerror=cb_except.onerror)
def cb_screen_movecursor(pos, oldpos, visible, user):
    callbacks = c.ffi.from_handle(user)
    pos = from_native(pos, cls=Pos)
    oldpos = from_native(oldpos, cls=Pos)
    return callbacks.movecursor(pos, oldpos, visible)
@c.ffi.def_extern(onerror=cb_except.onerror)
def cb_screen_settermprop(prop, val, user):
    callbacks = c.ffi.from_handle(user)
    prop = from_native(prop, cls=Prop)
    val = from_native(val, prop=prop)
    return callbacks.settermprop(prop, val)
@c.ffi.def_extern(onerror=cb_except.onerror)
def cb_screen_bell(user):
    callbacks = c.ffi.from_handle(user)
    return callbacks.bell()
@c.ffi.def_extern(onerror=cb_except.onerror)
def cb_screen_resize(rows, cols, user):
    callbacks = c.ffi.from_handle(user)
    return callbacks.resize(Size(rows=rows, cols=cols))
@c.ffi.def_extern(onerror=cb_except.onerror)
def cb_screen_sb_pushline(cols, cells, user):
    callbacks = c.ffi.from_handle(user)
    # TODO - passing the native elements
    return callbacks.sb_pushline(tuple(cells[0:cols]))
@c.ffi.def_extern(onerror=cb_except.onerror)
def cb_screen_sb_popline(cols, cells, user):
    callbacks = c.ffi.from_handle(user)
    # TODO - passing the native object and elements
    return callbacks.sb_popline(cells[0:cols])

_g_screen_callbacks = c.ffi.new('VTermScreenCallbacks*')
_g_screen_callbacks.damage = c.cb_screen_damage.__wrapped__
_g_screen_callbacks.moverect = c.cb_screen_moverect.__wrapped__
_g_screen_callbacks.movecursor = c.cb_screen_movecursor.__wrapped__
_g_screen_callbacks.settermprop = c.cb_screen_settermprop.__wrapped__
_g_screen_callbacks.bell = c.cb_screen_bell.__wrapped__
_g_screen_callbacks.resize = c.cb_screen_resize.__wrapped__
_g_screen_callbacks.sb_pushline = c.cb_screen_sb_pushline.__wrapped__
_g_screen_callbacks.sb_popline = c.cb_screen_sb_popline.__wrapped__


@c.ffi.def_extern(onerror=cb_except.onerror)
def cb_scroll_rect_moverect(src, dest, user):
    fn = c.ffi.from_handle(user)
    return fn(src, dest)
@c.ffi.def_extern(onerror=cb_except.onerror)
def cb_scroll_rect_eraserect(rect, selective, user):
    fn = c.ffi.from_handle(user)
    return fn(rect, selective)


@c.ffi.def_extern(onerror=cb_except.onerror)
def cb_copy_cells_copycell(dest, src, user):
    fn = c.ffi.from_handle(user)
    return fn(dest, src)


def to_native(obj, **restriction):
    cls, ufield = _get_cls(**restriction)
    if type(obj) is not cls:
        raise TypeError('must be %s, not %s' % (cls.__name__, type(obj).__name__))
    if ufield is not None:
        c_obj = c.ffi.new('VTermValue*')
        if cls is Color:
            obj = to_native(obj, cls=cls)
        setattr(c_obj, ufield, obj)
        return c_obj
    if cls.fields is None:
        # use int directly, not pointer-to-enum
        #return c.ffi.new(cls.c_type, obj.value)
        return obj.value
    return c.ffi.new(cls.c_type, [getattr(obj, x) for x in cls.fields])

def from_native(c_obj, **restriction):
    cls, ufield = _get_cls(**restriction)
    if ufield is not None:
        rv = getattr(c_obj, ufield)
        if cls is Color:
            rv = from_native(rv, cls=cls)
        elif cls is bool:
            rv = bool(rv)
        elif cls is bytes:
            rv = c.ffi.string(rv)
        return rv
    if cls.fields is None:
        return cls(c_obj)
    return cls(*[getattr(c_obj, x) for x in cls.fields])

def _get_cls(cls=None, prop=None, attr=None):
    if (cls, prop, attr).count(None) != 2:
        raise TypeError('Must specify exactly one restriction')
    if cls is not None:
        return cls, None
    if prop is not None:
        value_type = c.vterm_get_prop_type(prop.value)
    if attr is not None:
        value_type = c.vterm_get_attr_type(attr.value)
    return _value_type_to_cls[ValueType(value_type)]
_value_type_to_cls = {
    ValueType.BOOL: (bool, 'boolean'),
    ValueType.INT: (int, 'number'),
    ValueType.STRING: (bytes, 'string'),
    ValueType.COLOR: (Color, 'color'),
}
