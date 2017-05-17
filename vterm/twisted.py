import sys

from twisted.internet import abstract
from twisted.internet import fdesc
#from twisted.internet import reactor # delay until as late as possible
from twisted.internet import stdio

from . import core, pty


def same_attrs(a, b):
    return a.attrs == b.attrs and a.fg == b.fg and a.bg == b.bg


class TwistedPtyCallbacks(pty.PtyCallbacks):
    ''' These are callbacks for the VTerm's internal events.
    '''
    def __init__(self, vt, *, reactor, exclusive=False):
        super().__init__(vt)
        self.reactor = reactor
        self.fd = TwistedVtermPtyFileDescriptor(vt, reactor=reactor, exclusive=exclusive)
        self.fd.startReading()
        self.saved_cells = []

    def damage(self, rect):
        print('damage', rect)
        for row in range(rect.start_row, rect.end_row):
            cells = []
            col_range = iter(range(rect.start_col, rect.end_col))
            for col in col_range:
                cell = self.vt.get_cell(core.Pos(row=row, col=col))
                if cell.width == 2:
                    next(col_range)
                if cells and same_attrs(cells[-1][0], cell):
                    cells[-1].append(cell)
                else:
                    cells.append([])
                    cells[-1].append(cell)
            print(' cells', cells)
        return 0
    def moverect(self, dest, src):
        print('moverect', dest, src)
        return 0
    def movecursor(self, pos, oldpos, visible):
        print('movecursor', pos, oldpos, visible)
        return 0
    def settermprop(self, prop, val):
        print('settermprop', prop, val)
        return 0
    def bell(self):
        print('bell')
        return 0
    def resize(self, size):
        print('resize', size)
        return 0


class TwistedVtermPtyFileDescriptor(abstract.FileDescriptor):
    ''' These are callbacks for file descriptor events.
    '''
    def __init__(self, vt, *, reactor, exclusive=False):
        super().__init__(reactor=reactor)
        self.vt = vt
        self.exclusive = exclusive

    def connectionLost(self, reason):
        if self.exclusive:
            self.reactor.stop()

    def writeSomeData(self, data):
        return fdesc.writeToFD(self.fileno(), data)

    def doRead(self):
        rv = fdesc.readFromFD(self.fileno(), self.vt.input_write)
        o = self.vt.output_read()
        self.write(o)
        self.vt.flush_damage()
        return rv

    def fileno(self):
        return self.vt._master_fd


class TwistedTieProto():
    def __init__(self, fd):
        super().__init__()
        self.fd = fd

    def makeConnection(self, transport):
        pass

    def dataReceived(self, data):
        self.fd.write(data)

    def connectionLost(self, reason):
        pass


def main():
    want_stdio = sys.argv[1] != '--no-stdio'
    if not want_stdio:
        del sys.argv[1]

    # for use with `python -i`
    global reactor, vt, tie_proto, tie_stdio
    from twisted.internet import reactor
    vt = pty.VTermPty(sys.argv[1:], callbacks_cls=TwistedPtyCallbacks, reactor=reactor, exclusive=True)
    vt.set_damage_merge(core.DamageSize.SCROLL)
    if want_stdio:
        tie_proto = TwistedTieProto(vt.callbacks.fd)
        tie_stdio = stdio.StandardIO(tie_proto, reactor=reactor)
        tie_stdio.startReading()
        fdesc.setBlocking(1)
    reactor.run()


if __name__ == '__main__':
    main()
