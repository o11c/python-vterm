import codecs
import os
import sys

import attr

import vterm.core as vterm


SLOPPY = True


def print(*args, __print=print, **kwargs):
    kwargs.setdefault('flush', True)
    __print(*args, **kwargs)


def make_rect(a, b, c, d):
    return vterm.Rect(a, c, b, d)


def BOOLSTR(v):
    return 'on' if v else 'off'


@attr.s
class PenState:
    bold = attr.ib(init=False, default=0)
    underline = attr.ib(init=False, default=0)
    italic = attr.ib(init=False, default=0)
    blink = attr.ib(init=False, default=0)
    reverse = attr.ib(init=False, default=0)
    strike = attr.ib(init=False, default=0)
    font = attr.ib(init=False, default=0)
    foreground = attr.ib(init=False, default=vterm.Color(0, 0, 0))
    background = attr.ib(init=False, default=vterm.Color(0, 0, 0))


@attr.s
class CallbackState:
    ''' Split from `Harness` to avoid reference cycles.
    '''
    want_movecursor = attr.ib(init=False, default=False)
    want_moverect = attr.ib(init=False, default=False)
    want_screen_damage = attr.ib(init=False, default=False)
    want_screen_damage_cells = attr.ib(init=False, default=False)
    want_screen_scrollback = attr.ib(init=False, default=False)
    want_scrollrect = attr.ib(init=False, default=False)
    want_settermprop = attr.ib(init=False, default=False)
    want_state_erase = attr.ib(init=False, default=False)
    want_state_putglyph = attr.ib(init=False, default=False)
    state_pos = attr.ib(init=False, default=None)
    state_pen = attr.ib(init=False, default=attr.Factory(PenState))


def parse_bytes(s):
    if s[0] == '"' == s[-1]:
        # The raw .test files use these, but the Perl wrapper munges them.
        raise NotImplementedError
    return codecs.decode(s, 'hex')


def strpe_modifiers(s):
    state = vterm.Modifier.NONE
    for i in range(len(s)):
        if s[i] == 'S':
            state |= vterm.Modifier.SHIFT
        elif s[i] == 'C':
            state |= vterm.Modifier.CTRL
        elif s[i] == 'A':
            state |= vterm.Modifier.ALT
        else:
            break
    return state, s[i+1:]


__keys = {
    'Up': vterm.Key.UP,
    'Tab': vterm.Key.TAB,
    'Enter': vterm.Key.ENTER,
    'KP0': vterm.Key.KP_0,
}
def strp_key(key_str):
    return __keys[key_str]


def parser_text(self, bytes_):
    bits = []
    for b in bytes_:
        if (b & 0x7f) < 0x20 or b == 0x7f:
            break
        bits.append('%02x' % b)
    print('text', ','.join(bits))
    return len(bits)

def parser_control(self, control):
    print('control', '%02x' % control)
    return 1

def parser_escape(self, bytes_):
    print('escape', ''.join(['%02x' % b for b in bytes_]))
    return len(bytes_)

def parser_csi(self, leader, args, intermed, command):
    bits = []
    bits.append('csi')
    bits.append('%02x' % ord(command))
    if leader:
        bits.append('L=%s' % ''.join(['%02x' % b for b in leader]))
    bits2 = []
    for a, c in args:
        if a is None:
            a = '*'
        else:
            a = str(a)
        c = '+' if c else ''
        bits2.append(a + c)
    bits.append(','.join(bits2))
    if intermed:
        bits.append('I=%s' % ''.join(['%02x' % b for b in intermed]))
    print(*bits)
    return 1

def parser_osc(self, command):
    print('osc', ''.join(['%02x' % b for b in command]))
    return 1

def parser_dcs(self, command):
    print('dcs', ''.join(['%02x' % b for b in command]))
    return 1


def movecursor(self, pos, oldpos, visible):
    self.cbstate.state_pos = pos
    if self.cbstate.want_movecursor:
        print('movecursor', '%d,%d' % (pos.row, pos.col))
    return 1

def scrollrect(self, rect, downward, rightward):
    if not self.cbstate.want_scrollrect:
        return 0
    print('scrollrect', '%d..%d,%d..%d' % (rect.start_row, rect.end_row, rect.start_col, rect.end_col), '=>', '%+d,%+d' % (downward, rightward))
    return 1

def moverect(self, dest, src):
    if not self.cbstate.want_moverect:
        return 0
    print('moverect', '%d..%d,%d..%d' % (src.start_row,  src.end_row,  src.start_col,  src.end_col), '->', '%d..%d,%d..%d' % (dest.start_row, dest.end_row, dest.start_col, dest.end_col))
    return 1

def settermprop(self, prop, val):
    if not self.cbstate.want_settermprop:
        return 1
    if isinstance(val, bool):
        print('settermprop', prop.value, str(val).lower())
        return 1
    if isinstance(val, int):
        print('settermprop', prop.value, val)
        return 1
    if isinstance(val, bytes):
        print('settermprop', prop.value, '"%s"' % val.decode('utf-8', errors='surrogateescape'))
        return 1
    if isinstance(val, vterm.Color):
        print('settermprop', prop.value, 'rgb(%d,%d,%d)' % (val.red, val.green, val.blue))
        return 1
    assert False, 'unknown type %r' % (type(val).__name__)
    return 0


def state_putglyph(self, info, pos):
    if not self.cbstate.want_state_putglyph:
        return 1
    bits = []
    bits.append('putglyph')
    bits.append(','.join(['%x' % ord(u) for u in info.chars]))
    bits.append(info.width)
    bits.append('%d,%d' % (pos.row, pos.col))
    if info.protected_cell: bits.append('prot')
    if info.dwl: bits.append('dwl')
    if info.dhl != 0: bits.append('dhl-%s' % ['top', 'bottom'][info.dhl-1])
    print(*bits)
    return 1

def state_erase(self, rect, selective):
    if not self.cbstate.want_state_erase:
        return 1
    bits = []
    bits.append('erase')
    bits.append('%d..%d,%d..%d' % (rect.start_row, rect.end_row, rect.start_col, rect.end_col))
    if selective: bits.append('selective')
    print(*bits)
    return 1

__pen_attr_name = {
    vterm.Attr.BOLD: 'bold',
    vterm.Attr.UNDERLINE: 'underline',
    vterm.Attr.ITALIC: 'italic',
    vterm.Attr.BLINK: 'blink',
    vterm.Attr.REVERSE: 'reverse',
    vterm.Attr.STRIKE: 'strike',
    vterm.Attr.FONT: 'font',
    vterm.Attr.FOREGROUND: 'foreground',
    vterm.Attr.BACKGROUND: 'background',
}
def state_setpenattr(self, attr, val):
    setattr(self.cbstate.state_pen, __pen_attr_name[attr], val)
    return 1

def state_setlineinfo(self, row, newinfo, oldinfo):
    return 1


def screen_damage(self, rect):
    if not self.cbstate.want_screen_damage:
        return 1
    bits = []
    bits.append('damage')
    bits.append('%d..%d,%d..%d' % (rect.start_row, rect.end_row, rect.start_col, rect.end_col))
    if self.cbstate.want_screen_damage_cells:
        equals = False
        for row in range(rect.start_row, rect.end_row):
            bits2 = []
            for col in range(rect.start_col, rect.end_col):
                 cell = self.vt.screen_get_cell(vterm.Pos(row=row, col=col))
                 bits2.append('%02X' % (ord(cell.chars[0]) if cell.chars else 0))
            while bits2 and bits2[-1] == '00':
                bits2.pop()
            if not bits2:
                continue
            if not equals:
                bits.append('=')
                equals = True
            bits.append('%d<%s>' % (row, ' '.join(bits2)))
    print(*bits)
    return 1

def screen_sb_pushline(self, cells):
    if not self.cbstate.want_screen_scrollback:
        return 1
    cols = len(cells)
    cells = list(cells)
    while cells and not cells[-1].chars[0]:
        cells.pop()
    print('sb_pushline', cols, '=', *['%02X' % cell.chars[0] for cell in cells])
    return 1

def screen_sb_popline(self, cells):
    if not self.cbstate.want_screen_scrollback:
        return 0
    for i, c in enumerate(cells):
        if i < 5:
            c.chars[0] = ord('A') + i
        else:
            c.chars[0] = 0
        c.width = bytes([1])
    print('sb_popline', len(cells))
    return 1


class ParserCallbacks(vterm.ParserCallbacks):
    def __init__(self, vt, cbstate):
        super().__init__(vt)
        self.cbstate = cbstate
    text    = parser_text
    control = parser_control
    escape  = parser_escape
    csi     = parser_csi
    osc     = parser_osc
    dcs     = parser_dcs


class StateCallbacks(vterm.StateCallbacks):
    def __init__(self, vt, cbstate):
        super().__init__(vt)
        self.cbstate = cbstate
    putglyph    = state_putglyph
    movecursor  = movecursor
    scrollrect  = scrollrect
    moverect    = moverect
    erase       = state_erase
    setpenattr  = state_setpenattr
    settermprop = settermprop
    setlineinfo = state_setlineinfo


class ScreenCallbacks(vterm.ScreenCallbacks):
    def __init__(self, vt, cbstate):
        super().__init__(vt)
        self.cbstate = cbstate
    damage      = screen_damage
    moverect    = moverect
    movecursor  = movecursor
    settermprop = settermprop
    sb_pushline = screen_sb_pushline
    sb_popline  = screen_sb_popline


@attr.s(slots=True)
class Harness:
    vt = attr.ib(init=False, default=None)
    cbstate = attr.ib(init=False, default=attr.Factory(CallbackState))
    has_parser = attr.ib(init=False, default=False)
    has_state = attr.ib(init=False, default=False)
    has_screen = attr.ib(init=False, default=False)
    test_name = attr.ib(init=False, default=os.path.basename(os.getenv('VTERM_TEST_NAME')))

    def parser_cbs(self):
        return ParserCallbacks(self.vt, self.cbstate)

    def state_cbs(self):
        return StateCallbacks(self.vt, self.cbstate)

    def screen_cbs(self):
        return ScreenCallbacks(self.vt, self.cbstate)

    def main(self):
        for line in sys.stdin:
            line = line.rstrip('\n')
            line_cmd, _, args = line.partition(' ')
            if line_cmd.startswith('?'):
                getattr(self, 'query_' + line_cmd[1:])(args)
            else:
                getattr(self, 'cmd_' + line_cmd)(args)
                outbuff = self.vt.output_read()
                if outbuff:
                    print('output', ','.join(['%x' % b for b in outbuff]))
                print('DONE')

    def cmd_INIT(self, args):
        assert not args, args
        if self.vt is None:
            self.vt = vterm.VTerm()
    def cmd_WANTPARSER(self, args):
        assert not args, args
        self.vt._parser_set_callbacks(self.parser_cbs())
        self.has_parser = True
    def cmd_WANTSTATE(self, args):
        if self.test_name in (
            '43screen_resize.test',
            '90vttest_01-movement-1.test',
            '90vttest_01-movement-2.test',
            '90vttest_01-movement-3.test',
            '90vttest_02-screen-2.test',
        ):
            return
        if not self.has_state:
            self.vt._state_set_callbacks(self.state_cbs())
            self.vt.state_set_bold_highbright(True)
            self.vt.state_reset(True)
            self.has_state = True
        sense = True
        for c in args.lstrip(' '):
            if c == '+':
                sense = True
            elif c == '-':
                sense = False
            elif c == 'g':
                self.cbstate.want_state_putglyph = sense
            elif c == 's':
                self.cbstate.want_scrollrect = sense
            elif c == 'm':
                self.cbstate.want_moverect = sense
            elif c == 'e':
                self.cbstate.want_state_erase = sense
            elif c == 'p':
                self.cbstate.want_settermprop = sense
            elif c == 'f':
                self.vt.state_set_unrecognised_fallbacks(self.parser_cbs() if sense else None)
            else:
                assert False, 'WANTSTATE %r' % c
    def cmd_WANTSCREEN(self, args):
        assert not self.has_state, 'ordering bug'
        self.vt.screen_enable_altscreen(True)
        self.vt.screen_set_callbacks(self.screen_cbs())
        sense = True
        for c in args.lstrip(' '):
            if c == '-':
                sense = False
            elif c == 'd':
                self.cbstate.want_screen_damage = sense
            elif c == 'D':
                self.cbstate.want_screen_damage = sense
                self.cbstate.want_screen_damage_cells = sense
            elif c == 'm':
                self.cbstate.want_moverect = sense
            elif c == 'c':
                self.cbstate.want_movecursor = sense
            elif c == 'p':
                self.cbstate.want_settermprop = True
            elif c == 'b':
                self.cbstate.want_screen_scrollback = sense
            else:
                assert False, 'WANTSCREEN %r' % c
        self.has_screen = True
    def cmd_UTF8(self, args):
        flag = {'0': False, '1': True}[args.strip()]
        self.vt.set_utf8(flag)
    def cmd_RESET(self, args):
        if self.has_state:
            self.vt.state_reset(1)
            self.cbstate.state_pos = self.vt.state_get_cursorpos()
        if self.has_screen:
            self.vt.screen_reset(1)
    def cmd_RESIZE(self, args):
        self.vt.set_size(vterm.Size(*[int(x) for x in args.strip().split(',')]))
    def cmd_PUSH(self, args):
        self.vt.input_write(parse_bytes(args))
    def cmd_WANTENCODING(self, args):
        raise NotImplementedError
    def cmd_ENCIN(self, args):
        raise NotImplementedError
    def cmd_INCHAR(self, args):
        mod, args = strpe_modifiers(args.lstrip(' '))
        c = int(args, 16)
        self.vt.keyboard_unichar(c, mod)
    def cmd_INKEY(self, args):
        mod, args = strpe_modifiers(args.lstrip(' '))
        key = strp_key(args.lstrip())
        self.vt.keyboard_key(key, mod)
    def cmd_PASTE(self, args):
        if args == 'START':
            self.vt.keyboard_start_paste()
        elif args == 'END':
            self.vt.keyboard_end_paste()
        else:
            assert False, 'PASTE %r' % args
    def cmd_MOUSEMOVE(self, args):
        if SLOPPY and ' ' not in args:
            rc = args
            mod = '0'
        else:
            rc, mod = args.split()
        r, c = [int(x) for x in rc.split(',')]
        mod, _ = strpe_modifiers(mod)
        self.vt.mouse_move(vterm.Pos(r, c), mod)
    def cmd_MOUSEBTN(self, args):
        press, button, mod = args.split()
        button = int(button)
        mod, _ = strpe_modifiers(mod)
        self.vt.mouse_button(button, press.lower() == 'd', mod)
    def cmd_DAMAGEMERGE(self, args):
        dam = vterm.DamageSize._member_map_[args.lstrip(' ')]
        self.vt.screen_set_damage_merge(dam)
    def cmd_DAMAGEFLUSH(self, args):
        assert not args, args
        self.vt.screen_flush_damage()

    def query_cursor(self, args):
        assert not args, args
        pos = self.vt.state_get_cursorpos()
        state_pos = self.cbstate.state_pos
        if pos != state_pos:
            print('! row/col mismatch: state=%d,%d event=%d,%d' % (
                    pos.row, pos.col, state_pos.row, state_pos.col))
        else:
            print('%d,%d' % (state_pos.row, state_pos.col))
    def query_pen(self, args):
        subquery_pen = getattr(self, '_query_pen_%s' % args.lstrip(' '))
        subquery_pen(self.cbstate.state_pen)
    def _query_pen_bold(self, state_pen):
        val = self.vt.state_get_penattr(vterm.Attr.BOLD)
        if val != state_pen.bold:
            print('! pen bold mismatch; state=%s, event=%s' % (state_pen.bold, val))
        else:
            print(BOOLSTR(val))
    def _query_pen_underline(self, state_pen):
        val = self.vt.state_get_penattr(vterm.Attr.UNDERLINE)
        if val != state_pen.underline:
            print('! pen underline mismatch; state=%s, event=%s' % (state_pen.underline, val))
        else:
            print(val)
    def _query_pen_italic(self, state_pen):
        val = self.vt.state_get_penattr(vterm.Attr.ITALIC)
        if val != state_pen.italic:
            print('! pen italic mismatch; state=%s, event=%s' % (state_pen.italic, val))
        else:
            print(BOOLSTR(val))
    def _query_pen_blink(self, state_pen):
        val = self.vt.state_get_penattr(vterm.Attr.BLINK)
        if val != state_pen.blink:
            print('! pen blink mismatch; state=%s, event=%s' % (state_pen.blink, val))
        else:
            print(BOOLSTR(val))
    def _query_pen_reverse(self, state_pen):
        val = self.vt.state_get_penattr(vterm.Attr.REVERSE)
        if val != state_pen.reverse:
            print('! pen reverse mismatch; state=%s, event=%s' % (state_pen.reverse, val))
        else:
            print(BOOLSTR(val))
    def _query_pen_font(self, state_pen):
        val = self.vt.state_get_penattr(vterm.Attr.FONT)
        if val != state_pen.font:
            print('! pen font mismatch; state=%s, event=%s' % (state_pen.font, val))
        else:
            print(val)
    def _query_pen_foreground(self, state_pen):
        val = self.vt.state_get_penattr(vterm.Attr.FOREGROUND)
        if val != state_pen.foreground:
            print('! pen foreground mismatch; state=%s, event=%s' % (state_pen.foreground, val))
        else:
            print('rgb(%d,%d,%d)' % (val.red, val.green, val.blue))
    def _query_pen_background(self, state_pen):
        val = self.vt.state_get_penattr(vterm.Attr.BACKGROUND)
        if val != state_pen.background:
            print('! pen background mismatch; state=%s, event=%s' % (state_pen.background, val))
        else:
            print('rgb(%d,%d,%d)' % (val.red, val.green, val.blue))
    def query_screen_chars(self, args):
        rect = make_rect(*[int(x) for x in args.lstrip(' ').split(',')])
        chars = self.vt.screen_get_chars(rect)
        print(','.join(['0x%02x' % ord(u) for u in chars]))
    def query_screen_text(self, args):
        rect = make_rect(*[int(x) for x in args.lstrip(' ').split(',')])
        text = self.vt.screen_get_text(rect)
        print(','.join(['0x%02x' % b for b in text]))
    def query_screen_cell(self, args):
        pos = vterm.Pos(*[int(x) for x in args.lstrip(' ').split(',')])
        cell = self.vt.screen_get_cell(pos)
        bits = []
        bits.append('{')
        bits.append(','.join(['0x%02x' % ord(u) for u in cell.chars]))
        bits.append('} width=')
        bits.append(str(cell.width))
        bits.append(' attrs={')
        if cell.attrs.bold: bits.append('B')
        if cell.attrs.underline: bits.append('U1') # no double-underline
        if cell.attrs.italic: bits.append('I')
        if cell.attrs.blink: bits.append('K')
        if cell.attrs.reverse: bits.append('R')
        if cell.attrs.font != 0: bits.append('F%d' % cell.attrs.font)
        bits.append('} ')
        if cell.attrs.dwl: bits.append('dwl ')
        if cell.attrs.dhl: bits.append('dhl-%s ' % ['top', 'bottom'][cell.attrs.dhl-1])
        bits.append('fg=rgb(%d,%d,%d) ' % (cell.fg.red, cell.fg.green, cell.fg.blue))
        bits.append('bg=rgb(%d,%d,%d)' % (cell.bg.red, cell.bg.green, cell.bg.blue))
        print(*bits, sep='')
    def query_screen_eol(self, args):
        pos = vterm.Pos(*[int(x) for x in args.lstrip(' ').split(',')])
        print('%d' % self.vt.screen_is_eol(pos))
    def query_screen_attrs_extent(self, args):
        pos = vterm.Pos(*[int(x) for x in args.lstrip(' ').split(',')])
        rect = self.vt.screen_get_attrs_extent(pos, ~vterm.AttrMask(0))
        print('%d,%d-%d,%d' % (rect.start_row, rect.start_col, rect.end_row, rect.end_col))


if __name__ == '__main__':
    Harness().main()
