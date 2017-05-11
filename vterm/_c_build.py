import cffi
import pkg_resources

ffibuilder = cffi.FFI()
ffibuilder.cdef('''
typedef enum {
  VTERM_MOD_NONE  = 0x00,
  VTERM_MOD_SHIFT = 0x01,
  VTERM_MOD_ALT   = 0x02,
  VTERM_MOD_CTRL  = 0x04,
} VTermModifier;
''')
ffibuilder.cdef('''
typedef enum {
  VTERM_KEY_NONE,

  VTERM_KEY_ENTER,
  VTERM_KEY_TAB,
  VTERM_KEY_BACKSPACE,
  VTERM_KEY_ESCAPE,

  VTERM_KEY_UP,
  VTERM_KEY_DOWN,
  VTERM_KEY_LEFT,
  VTERM_KEY_RIGHT,

  VTERM_KEY_INS,
  VTERM_KEY_DEL,
  VTERM_KEY_HOME,
  VTERM_KEY_END,
  VTERM_KEY_PAGEUP,
  VTERM_KEY_PAGEDOWN,

  VTERM_KEY_FUNCTION_0   = 256,
  VTERM_KEY_FUNCTION_MAX = %(VTERM_KEY_FUNCTION_0 + 255)s,

  VTERM_KEY_KP_0,
  VTERM_KEY_KP_1,
  VTERM_KEY_KP_2,
  VTERM_KEY_KP_3,
  VTERM_KEY_KP_4,
  VTERM_KEY_KP_5,
  VTERM_KEY_KP_6,
  VTERM_KEY_KP_7,
  VTERM_KEY_KP_8,
  VTERM_KEY_KP_9,
  VTERM_KEY_KP_MULT,
  VTERM_KEY_KP_PLUS,
  VTERM_KEY_KP_COMMA,
  VTERM_KEY_KP_MINUS,
  VTERM_KEY_KP_PERIOD,
  VTERM_KEY_KP_DIVIDE,
  VTERM_KEY_KP_ENTER,
  VTERM_KEY_KP_EQUAL,

  VTERM_KEY_MAX,
} VTermKey;
''' % {'VTERM_KEY_FUNCTION_0 + 255': 256 + 255})
ffibuilder.cdef('''
typedef struct VTerm VTerm;
typedef struct VTermState VTermState;
typedef struct VTermScreen VTermScreen;
''')
ffibuilder.cdef('''
typedef struct {
  int row;
  int col;
} VTermPos;
''')
ffibuilder.cdef('''
typedef struct {
  int start_row;
  int end_row;
  int start_col;
  int end_col;
} VTermRect;
''')
ffibuilder.cdef('''
typedef struct {
  uint8_t red, green, blue;
} VTermColor;
''')
ffibuilder.cdef('''
typedef enum {
  VTERM_VALUETYPE_BOOL = 1,
  VTERM_VALUETYPE_INT,
  VTERM_VALUETYPE_STRING,
  VTERM_VALUETYPE_COLOR,
} VTermValueType;
''')
ffibuilder.cdef('''
typedef union {
  int boolean;
  int number;
  char *string;
  VTermColor color;
} VTermValue;
''')
ffibuilder.cdef('''
typedef enum {
  VTERM_ATTR_BOLD = 1,
  VTERM_ATTR_UNDERLINE,
  VTERM_ATTR_ITALIC,
  VTERM_ATTR_BLINK,
  VTERM_ATTR_REVERSE,
  VTERM_ATTR_STRIKE,
  VTERM_ATTR_FONT,
  VTERM_ATTR_FOREGROUND,
  VTERM_ATTR_BACKGROUND,
} VTermAttr;
''')
ffibuilder.cdef('''
typedef enum {
  VTERM_PROP_CURSORVISIBLE = 1,
  VTERM_PROP_CURSORBLINK,
  VTERM_PROP_ALTSCREEN,
  VTERM_PROP_TITLE,
  VTERM_PROP_ICONNAME,
  VTERM_PROP_REVERSE,
  VTERM_PROP_CURSORSHAPE,
  VTERM_PROP_MOUSE,
} VTermProp;
''')
ffibuilder.cdef('''
enum {
  VTERM_PROP_CURSORSHAPE_BLOCK = 1,
  VTERM_PROP_CURSORSHAPE_UNDERLINE,
  VTERM_PROP_CURSORSHAPE_BAR_LEFT,
};
''')
ffibuilder.cdef('''
enum {
  VTERM_PROP_MOUSE_NONE = 0,
  VTERM_PROP_MOUSE_CLICK,
  VTERM_PROP_MOUSE_DRAG,
  VTERM_PROP_MOUSE_MOVE,
};
''')
ffibuilder.cdef('''
typedef struct {
  const uint32_t *chars;
  int             width;
  unsigned int    protected_cell:1;
  unsigned int    dwl:1;
  unsigned int    dhl:2;
} VTermGlyphInfo;
''')
ffibuilder.cdef('''
typedef struct {
  unsigned int    doublewidth:1;
  unsigned int    doubleheight:2;
} VTermLineInfo;
''')
ffibuilder.cdef('''
typedef struct {
  void *(*malloc)(size_t size, void *allocdata);
  void  (*free)(void *ptr, void *allocdata);
} VTermAllocatorFunctions;
''')
ffibuilder.cdef('''
VTerm *vterm_new(int rows, int cols);
VTerm *vterm_new_with_allocator(int rows, int cols, VTermAllocatorFunctions *funcs, void *allocdata);
void   vterm_free(VTerm* vt);
''')
ffibuilder.cdef('''
void vterm_get_size(const VTerm *vt, int *rowsp, int *colsp);
void vterm_set_size(VTerm *vt, int rows, int cols);
''')
ffibuilder.cdef('''
int  vterm_get_utf8(const VTerm *vt);
void vterm_set_utf8(VTerm *vt, int is_utf8);
''')
ffibuilder.cdef('''
size_t vterm_input_write(VTerm *vt, const char *bytes, size_t len);
''')
ffibuilder.cdef('''
size_t vterm_output_get_buffer_size(const VTerm *vt);
size_t vterm_output_get_buffer_current(const VTerm *vt);
size_t vterm_output_get_buffer_remaining(const VTerm *vt);
''')
ffibuilder.cdef('''
size_t vterm_output_read(VTerm *vt, char *buffer, size_t len);
''')
ffibuilder.cdef('''
void vterm_keyboard_unichar(VTerm *vt, uint32_t c, VTermModifier mod);
void vterm_keyboard_key(VTerm *vt, VTermKey key, VTermModifier mod);
''')
ffibuilder.cdef('''
void vterm_keyboard_start_paste(VTerm *vt);
void vterm_keyboard_end_paste(VTerm *vt);
''')
ffibuilder.cdef('''
void vterm_mouse_move(VTerm *vt, int row, int col, VTermModifier mod);
void vterm_mouse_button(VTerm *vt, int button, bool pressed, VTermModifier mod);
''')
ffibuilder.cdef('''
typedef struct {
  int (*text)(const char *bytes, size_t len, void *user);
  int (*control)(unsigned char control, void *user);
  int (*escape)(const char *bytes, size_t len, void *user);
  int (*csi)(const char *leader, const long args[], int argcount, const char *intermed, char command, void *user);
  int (*osc)(const char *command, size_t cmdlen, void *user);
  int (*dcs)(const char *command, size_t cmdlen, void *user);
  int (*resize)(int rows, int cols, void *user);
} VTermParserCallbacks;
''')
ffibuilder.cdef('''
extern "Python" {
  int cb_parser_text(const char *bytes, size_t len, void *user);
  int cb_parser_control(unsigned char control, void *user);
  int cb_parser_escape(const char *bytes, size_t len, void *user);
  int cb_parser_csi(const char *leader, const long args[], int argcount, const char *intermed, char command, void *user);
  int cb_parser_osc(const char *command, size_t cmdlen, void *user);
  int cb_parser_dcs(const char *command, size_t cmdlen, void *user);
  int cb_parser_resize(int rows, int cols, void *user);
}
''')
ffibuilder.cdef('''
void  vterm_parser_set_callbacks(VTerm *vt, const VTermParserCallbacks *callbacks, void *user);
void *vterm_parser_get_cbdata(VTerm *vt);
''')
ffibuilder.cdef('''
typedef struct {
  int (*putglyph)(VTermGlyphInfo *info, VTermPos pos, void *user);
  int (*movecursor)(VTermPos pos, VTermPos oldpos, int visible, void *user);
  int (*scrollrect)(VTermRect rect, int downward, int rightward, void *user);
  int (*moverect)(VTermRect dest, VTermRect src, void *user);
  int (*erase)(VTermRect rect, int selective, void *user);
  int (*initpen)(void *user);
  int (*setpenattr)(VTermAttr attr, VTermValue *val, void *user);
  int (*settermprop)(VTermProp prop, VTermValue *val, void *user);
  int (*bell)(void *user);
  int (*resize)(int rows, int cols, VTermPos *delta, void *user);
  int (*setlineinfo)(int row, const VTermLineInfo *newinfo, const VTermLineInfo *oldinfo, void *user);
} VTermStateCallbacks;
''')
ffibuilder.cdef('''
extern "Python" {
  int cb_state_putglyph(VTermGlyphInfo *info, VTermPos pos, void *user);
  int cb_state_movecursor(VTermPos pos, VTermPos oldpos, int visible, void *user);
  int cb_state_scrollrect(VTermRect rect, int downward, int rightward, void *user);
  int cb_state_moverect(VTermRect dest, VTermRect src, void *user);
  int cb_state_erase(VTermRect rect, int selective, void *user);
  int cb_state_initpen(void *user);
  int cb_state_setpenattr(VTermAttr attr, VTermValue *val, void *user);
  int cb_state_settermprop(VTermProp prop, VTermValue *val, void *user);
  int cb_state_bell(void *user);
  int cb_state_resize(int rows, int cols, VTermPos *delta, void *user);
  int cb_state_setlineinfo(int row, const VTermLineInfo *newinfo, const VTermLineInfo *oldinfo, void *user);
}
''')
ffibuilder.cdef('''
VTermState *vterm_obtain_state(VTerm *vt);
''')
ffibuilder.cdef('''
void  vterm_state_set_callbacks(VTermState *state, const VTermStateCallbacks *callbacks, void *user);
void *vterm_state_get_cbdata(VTermState *state);
''')
ffibuilder.cdef('''
void  vterm_state_set_unrecognised_fallbacks(VTermState *state, const VTermParserCallbacks *fallbacks, void *user);
void *vterm_state_get_unrecognised_fbdata(VTermState *state);
''')
ffibuilder.cdef('''
void vterm_state_reset(VTermState *state, int hard);
void vterm_state_get_cursorpos(const VTermState *state, VTermPos *cursorpos);
void vterm_state_get_default_colors(const VTermState *state, VTermColor *default_fg, VTermColor *default_bg);
void vterm_state_get_palette_color(const VTermState *state, int index, VTermColor *col);
void vterm_state_set_default_colors(VTermState *state, const VTermColor *default_fg, const VTermColor *default_bg);
void vterm_state_set_palette_color(VTermState *state, int index, const VTermColor *col);
void vterm_state_set_bold_highbright(VTermState *state, int bold_is_highbright);
int  vterm_state_get_penattr(const VTermState *state, VTermAttr attr, VTermValue *val);
int  vterm_state_set_termprop(VTermState *state, VTermProp prop, VTermValue *val);
const VTermLineInfo *vterm_state_get_lineinfo(const VTermState *state, int row);
''')
ffibuilder.cdef('''
typedef struct {
  uint32_t chars[%(VTERM_MAX_CHARS_PER_CELL)s];
  char     width;
  struct {
    unsigned int bold      : 1;
    unsigned int underline : 2;
    unsigned int italic    : 1;
    unsigned int blink     : 1;
    unsigned int reverse   : 1;
    unsigned int strike    : 1;
    unsigned int font      : 4;
    unsigned int dwl       : 1;
    unsigned int dhl       : 2;
  } attrs;
  VTermColor fg, bg;
} VTermScreenCell;
''' % {'VTERM_MAX_CHARS_PER_CELL': 6})
ffibuilder.cdef('''
typedef struct {
  int (*damage)(VTermRect rect, void *user);
  int (*moverect)(VTermRect dest, VTermRect src, void *user);
  int (*movecursor)(VTermPos pos, VTermPos oldpos, int visible, void *user);
  int (*settermprop)(VTermProp prop, VTermValue *val, void *user);
  int (*bell)(void *user);
  int (*resize)(int rows, int cols, void *user);
  int (*sb_pushline)(int cols, const VTermScreenCell *cells, void *user);
  int (*sb_popline)(int cols, VTermScreenCell *cells, void *user);
} VTermScreenCallbacks;
''')
ffibuilder.cdef('''
extern "Python" {
  int cb_screen_damage(VTermRect rect, void *user);
  int cb_screen_moverect(VTermRect dest, VTermRect src, void *user);
  int cb_screen_movecursor(VTermPos pos, VTermPos oldpos, int visible, void *user);
  int cb_screen_settermprop(VTermProp prop, VTermValue *val, void *user);
  int cb_screen_bell(void *user);
  int cb_screen_resize(int rows, int cols, void *user);
  int cb_screen_sb_pushline(int cols, const VTermScreenCell *cells, void *user);
  int cb_screen_sb_popline(int cols, VTermScreenCell *cells, void *user);
}
''')
ffibuilder.cdef('''
VTermScreen *vterm_obtain_screen(VTerm *vt);
''')
ffibuilder.cdef('''
void  vterm_screen_set_callbacks(VTermScreen *screen, const VTermScreenCallbacks *callbacks, void *user);
void *vterm_screen_get_cbdata(VTermScreen *screen);
''')
ffibuilder.cdef('''
void  vterm_screen_set_unrecognised_fallbacks(VTermScreen *screen, const VTermParserCallbacks *fallbacks, void *user);
void *vterm_screen_get_unrecognised_fbdata(VTermScreen *screen);
''')
ffibuilder.cdef('''
void vterm_screen_enable_altscreen(VTermScreen *screen, int altscreen);
''')
ffibuilder.cdef('''
typedef enum {
  VTERM_DAMAGE_CELL,
  VTERM_DAMAGE_ROW,
  VTERM_DAMAGE_SCREEN,
  VTERM_DAMAGE_SCROLL,
} VTermDamageSize;
''')
ffibuilder.cdef('''
void vterm_screen_flush_damage(VTermScreen *screen);
void vterm_screen_set_damage_merge(VTermScreen *screen, VTermDamageSize size);
''')
ffibuilder.cdef('''
void   vterm_screen_reset(VTermScreen *screen, int hard);
''')
ffibuilder.cdef('''
size_t vterm_screen_get_chars(const VTermScreen *screen, uint32_t *chars, size_t len, const VTermRect rect);
size_t vterm_screen_get_text(const VTermScreen *screen, char *str, size_t len, const VTermRect rect);
''')
ffibuilder.cdef('''
typedef enum {
  VTERM_ATTR_BOLD_MASK       = %(1 << 0)s,
  VTERM_ATTR_UNDERLINE_MASK  = %(1 << 1)s,
  VTERM_ATTR_ITALIC_MASK     = %(1 << 2)s,
  VTERM_ATTR_BLINK_MASK      = %(1 << 3)s,
  VTERM_ATTR_REVERSE_MASK    = %(1 << 4)s,
  VTERM_ATTR_STRIKE_MASK     = %(1 << 5)s,
  VTERM_ATTR_FONT_MASK       = %(1 << 6)s,
  VTERM_ATTR_FOREGROUND_MASK = %(1 << 7)s,
  VTERM_ATTR_BACKGROUND_MASK = %(1 << 8)s,
} VTermAttrMask;
''' % {'1 << %d' % i: 1<<i for i in range(9)})
ffibuilder.cdef('''
int vterm_screen_get_attrs_extent(const VTermScreen *screen, VTermRect *extent, VTermPos pos, VTermAttrMask attrs);
''')
ffibuilder.cdef('''
int vterm_screen_get_cell(const VTermScreen *screen, VTermPos pos, VTermScreenCell *cell);
''')
ffibuilder.cdef('''
int vterm_screen_is_eol(const VTermScreen *screen, VTermPos pos);
''')
ffibuilder.cdef('''
VTermValueType vterm_get_attr_type(VTermAttr attr);
VTermValueType vterm_get_prop_type(VTermProp prop);
''')
ffibuilder.cdef('''
void vterm_scroll_rect(VTermRect rect,
                       int downward,
                       int rightward,
                       int (*moverect)(VTermRect src, VTermRect dest, void *user),
                       int (*eraserect)(VTermRect rect, int selective, void *user),
                       void *user);
''')
ffibuilder.cdef('''
extern "Python" {
                       int cb_scroll_rect_moverect(VTermRect src, VTermRect dest, void *user);
                       int cb_scroll_rect_eraserect(VTermRect rect, int selective, void *user);
}
''')
ffibuilder.cdef('''
void vterm_copy_cells(VTermRect dest,
                      VTermRect src,
                      void (*copycell)(VTermPos dest, VTermPos src, void *user),
                      void *user);
''')
ffibuilder.cdef('''
extern "Python" {
                      void cb_copy_cells_copycell(VTermPos dest, VTermPos src, void *user);
}
''')
ffibuilder.cdef('''
char *vterm_py_spawn_and_forget(char *cmd, char **argv, char **envp, int nfds, int *fds, int tty_fd);
void free(void *ptr);
''')

ffibuilder.set_source('vterm._c', '''
#include <vterm.h>
#include "c-sources/spawn.h"
''',
    sources=['vterm/c-sources/spawn.c', 'vterm/c-sources/correct-strerror_r.c'],
    include_dirs=None,
    define_macros=None,
    undef_macros=None,
    library_dirs=None,
    libraries=['vterm'],
    runtime_library_dirs=None,
    extra_objects=None,
    extra_compile_args=None,
    extra_link_args=None,
    export_symbols=None,
    swig_opts = None,
    depends=None,
    language=None,
    optional=None,
)

if __name__ == '__main__':
    ffibuilder.compile(verbose=True)
