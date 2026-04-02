"""Interactive console."""
import asyncio
import logging
import os
import sys
import termios
import tty
from pymscada.bus_client import BusClient
from pymscada.tag import Tag
from pymscada.www_server import standardise_tag_info


class EC:
    """Escape codes."""
    backspace = b'\x7f'
    enter = b'\r'
    tab = b'\t'
    up = b'\x1b[A'
    down = b'\x1b[B'
    right = b'\x1b[C'
    left = b'\x1b[D'
    end = b'\x1b[F'
    home = b'\x1b[H'
    cr_clr = b'\x1b[2K\x1b[G'  # clear line and move start
    clear_line = b'\x1b[2K'
    mv_start = b'\x1b[G'
    mv_left = b'\x1b[1000D'


class CustomHandler(logging.StreamHandler):
    """Control the cursor position."""

    def emit(self, record):
        """Write to the console adding a carriage return."""
        try:
            msg = self.format(record)
            msg = msg.replace('\n', '\r\n')
            self.stream.write(msg + '\r\n')
            self.stream.flush()
        except Exception:
            self.handleError(record)


class KeypressProtocol(asyncio.Protocol):
    """Handle key presses, one at a time."""

    def __init__(self, edit_line, process_command):
        """Set up line buffers and pointers."""
        self.edit_line = edit_line
        self.process_command = process_command
        self.lines = []
        self.history = None  # not showing history
        self.line = None  # not editing a line (yet)
        self.cursor = 0  # cursor position in line
        self.stash = None  # nothing stashed
        self.connection_lost_future = asyncio.Future()

    def data_received(self, data):
        """Got keypress, update edit line, send to writer."""
        if len(data) == 1:
            if data == EC.backspace and self.cursor > 0 and self.line:
                self.line = self.line[:self.cursor-1] + self.line[self.cursor:]
                self.cursor -= 1
            elif data == EC.enter:
                if self.line and (not self.lines or
                                  self.line != self.lines[-1]):
                    self.lines.append(self.line)
                self.stash = None
                self.edit_line(None, 0)
                self.process_command(self.line)
                self.line = None
                self.cursor = 0
                self.history = None
                return
            elif self.line is None:
                self.line = data
                self.cursor = 1
            else:
                self.line = (self.line[:self.cursor] + data
                             + self.line[self.cursor:])
                self.cursor += 1
        elif data == EC.left:
            if self.cursor > 0:
                self.cursor -= 1
        elif data == EC.right:
            if self.line and self.cursor < len(self.line):
                self.cursor += 1
        elif data == EC.up:
            if not self.lines:
                return
            if self.history is None:
                self.stash = self.line  # might be None
                self.history = len(self.lines)
            self.history -= 1
            if self.history < 0:
                self.history = 0
            self.line = self.lines[self.history]
            self.cursor = len(self.line)
        elif data == EC.down:
            if not self.lines or self.history is None:
                return
            self.history += 1
            if self.history == len(self.lines):
                self.line = self.stash
                self.history = None
            else:
                self.line = self.lines[self.history]
            if self.line is None:
                self.line = b''
            self.cursor = len(self.line)
        self.edit_line(self.line, self.cursor)

    def connection_lost(self, exc):
        """Let parent know protocol transport has disconnected."""
        self.connection_lost_future.set_result(True)


class ConsoleWriter:
    """Writer to group logging and console text."""

    @staticmethod
    def write_all(data: bytes) -> None:
        import select
        fd = sys.stdout.fileno()
        mv = memoryview(data)
        while len(mv):
            try:
                n = os.write(fd, mv)
                mv = mv[n:]
            except BlockingIOError:
                select.select([], [fd], [], None)

    def __init__(self):
        """Init."""
        self.edit = None
        self.cursor = 0
        import fcntl
        flags = fcntl.fcntl(sys.stdout.fileno(), fcntl.F_GETFL)
        fcntl.fcntl(sys.stdout.fileno(), fcntl.F_SETFL, flags | os.O_NONBLOCK)

    def write(self, data: bytes):
        """Stream writer, primarily for logging."""
        cursor_str = b''
        if self.edit is not None and self.cursor > 0:
            cursor_str = b'\x1b[' + str(self.cursor).encode() + b'C'
        ln = EC.cr_clr + data + b'\r\n'
        if self.edit is not None:
            ln += EC.cr_clr + self.edit + EC.mv_left + cursor_str
        self.write_all(ln)

    def edit_line(self, edit: bytes, cursor: int):
        """Update the edit line and cursor position."""
        self.edit = edit
        if self.edit is None:
            self.write_all(b'\r\n')
            return
        self.cursor = cursor
        ln = EC.cr_clr + self.edit + EC.mv_left
        if self.cursor > 0:
            ln += b'\x1b[' + str(self.cursor).encode() + b'C'
        self.write_all(ln)


class ConsoleTags:
    """Tag map from ``tag_info``, built after the bus client has started."""

    def __init__(self, tag_info: dict) -> None:
        self._by_name: dict[str, Tag] = {}
        for tagname, meta in tag_info.items():
            standardise_tag_info(tagname, meta)
            self._by_name[tagname] = Tag(tagname, meta['type'])

    def keys(self):
        return self._by_name.keys()

    def __getitem__(self, name: str) -> Tag:
        return self._by_name[name]

    def __contains__(self, name: str) -> bool:
        return name in self._by_name


class ConsoleManager:
    """Provide a text console to interact with a Bus."""

    def __init__(self, busclient: BusClient, tags: ConsoleTags) -> None:
        """TTY and logging after the bus client and tags exist."""
        self.busclient = busclient
        self.tags = tags
        self.fdin = sys.stdin.fileno()
        self.fdout = sys.stdout.fileno()
        self.fdin_attr = termios.tcgetattr(self.fdin)
        self.fdout_attr = termios.tcgetattr(self.fdout)
        tty.setraw(self.fdin)
        self.writer = ConsoleWriter()
        self.transport = None
        logger = logging.getLogger()
        handler = CustomHandler()
        handler.setFormatter(logging.Formatter('%(levelname)s console '
                                               '%(message)s'))
        logger.handlers.clear()
        logger.addHandler(handler)

    def write_tag(self, tag: Tag):
        """Append or insert tag value through writer."""
        ln = f'{tag.name} {tag.value}'.encode()
        self.writer.write(ln)

    def process(self, command: bytes):
        """Execute command."""
        if command is None:
            return
        c = command.lstrip().split(b' ', 2)
        cmd, var, val = (c + [None] * 3)[:3]
        tagname = None
        tagnames = list(self.tags.keys())
        if var is not None:
            tagname = var.decode()
            tagnames = [x for x in tagnames if tagname in x]
            if tagnames == []:
                tagname = None
        if cmd in [b'q', b'quit']:
            if self.transport is not None:
                self.transport.close()
        elif cmd in [b'g', b'get']:
            for tagname in tagnames:
                self.write_tag(self.tags[tagname])
        elif (cmd == b'set' and tagname is not None and val is not None):
            if tagname not in self.tags:
                self.writer.write(f'tag {tagname} not found'.encode())
                return
            try:
                typed_val = self.tags[tagname].type(val.decode())
                self.tags[tagname].value = typed_val
            except ValueError as e:
                logging.warning(f'error setting {tagname}: {e}')
        elif cmd in [b's', b'sub'] and tagname is not None:
            if tagname not in self.tags:
                self.writer.write(f'tag {tagname} not found'.encode())
                return
            self.tags[tagname].add_callback(self.write_tag)
            self.write_tag(self.tags[tagname])
        elif cmd in [b'u', b'unsub'] and tagname is not None:
            if self.write_tag in self.tags[tagname].pub:
                self.tags[tagname].del_callback(self.write_tag)
        elif cmd in [b'l', b'list']:
            ln = ' '.join(tagnames).encode()
            self.writer.write(ln)
        elif cmd in [b'h', b'help']:
            self.writer.write(
                b'list <match>              or l <match>\r\n'
                b'get <match>               or g <match>\r\n'
                b'set tagname value or string is cast to type\r\n'
                b'sub tagname               or s tagname\r\n'
                b'unsub <match>             or u <match>\r\n'
                b'---------------------------------------------')

    async def run(self):
        """Run until stdin closes or user quits."""
        try:
            protocol = \
                KeypressProtocol(self.writer.edit_line, self.process)
            loop = asyncio.get_running_loop()
            self.transport, _ = await loop.connect_read_pipe(
                lambda: protocol, sys.stdin)
            await protocol.connection_lost_future
        finally:
            termios.tcsetattr(self.fdout, termios.TCSADRAIN, self.fdout_attr)
            termios.tcsetattr(self.fdin, termios.TCSADRAIN, self.fdin_attr)


class Console:
    """Console interrogation of bus tag values."""

    def __init__(self, bus_ip: str = '127.0.0.1', bus_port: int = 1324,
                 tag_info=None) -> None:
        self.busclient = BusClient(bus_ip, bus_port, module='Console')
        self.tag_info = dict(tag_info) if tag_info else {}

    async def start(self):
        """Connect to the bus, then run the interactive console."""
        await self.busclient.start()
        self.tags = ConsoleTags(self.tag_info)
        manager = ConsoleManager(self.busclient, self.tags)
        await manager.run()
