import os

from . import c, core, util


def _no_eq(b):
    if b'=' in b:
        raise ValueError(b)
    return b


def _spawn(cmd, args, env=None, *, fds, tty=-1):
    if cmd is None:
        cmd = args[0]
    cmd = os.fsencode(cmd)
    args = [c.ffi.new('char[]', os.fsencode(a)) for a in args]
    args.append(c.ffi.NULL)

    if env is None:
        env = os.environ
    if tty != -1:
        env = env.copy()
        env['TERM'] = 'xterm-256color'
    env = [c.ffi.new('char[]', b'='.join([_no_eq(os.fsencode(k)), os.fsencode(v)])) for k, v in env.items()]
    env.append(c.ffi.NULL)

    fds = sorted(fds.items())
    c_fds = c.ffi.new('int[]', fds[-1][0] + 1)
    for k, v in fds:
        c_fds[k] = v

    error = c.ffi.gc(c.vterm_py_spawn_and_forget(cmd, args, env, len(c_fds), c_fds, tty), c.free)
    if error != c.ffi.NULL:
        raise OSError(c.ffi.string(error).decode('utf-8'))


class PtyCallbacks(core.ScreenCallbacks):
    def __init__(self, vt):
        super().__init__(vt)
        self.saved_cells = []

    def sb_pushline(self, cells):
        self.saved_cells.append(cells)
        return 1

    def sb_popline(self, cells_mut):
        if not self.saved_cells:
            return 0
        old_cells = self.saved_cells.pop()
        cells_len = min(len(old_cells), len(cells_mut))
        cells_mut[:len(cells_len)] = old_cells[:cells_len]
        return 1


class VTermPty(core.VTerm, util.Closing):
    __slots__ = ('_master_fd', '_slave_name', 'callbacks')
    def __init__(self, args, *, size=core.STANDARD_SIZE, cmd=None, env=None, callbacks_cls=PtyCallbacks, __os_close=os.close, **kwargs):
        self._master_fd = -1
        super().__init__(size)
        master_fd, slave_fd = os.openpty()
        try:
            self._slave_name = os.ttyname(slave_fd)
            _spawn(cmd, args, env, fds={0: slave_fd, 1: slave_fd, 2: slave_fd}, tty=slave_fd)

            self._master_fd = master_fd
            master_fd = -1
        finally:
            __os_close(slave_fd)
            if master_fd != -1:
                __os_close(master_fd)

        # configure some sensible defaults
        callbacks = callbacks_cls(self, **kwargs)
        self.set_callbacks(callbacks)
        self.callbacks = callbacks

    def __repr__(self):
        size = self.get_size()
        output = c.vterm_output_get_buffer_current(self._vt)
        slave = self._slave_name
        return '<%s size=%r output=%d slave=%r>' % (type(self).__name__, size, output, slave)

    @property
    def closed(self):
        return self._master_fd == -1

    def close(self, *, __os_close=os.close):
        master_fd = self._master_fd
        if master_fd != -1:
            __os_close(master_fd)
