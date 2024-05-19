"""Interactive console."""
import asyncio
import logging
import sys
import termios
import tty
from pymscada.bus_client import BusClient
from pymscada.tag import Tag, tag_for_web


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
    mv_left = b'\x1b[1000D'
    move_cursor_up = b'\x1b[1A'
    insert_line = b'\x1b[1L'


class KeypressReaderProtocol(asyncio.Protocol):
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

    def data_received(self, data):
        """Got keypress, update edit line, send to writer."""
        if len(data) == 1:
            if data == EC.backspace:
                self.line = self.line[:self.cursor-1] + self.line[self.cursor:]
                if self.cursor > 0:
                    self.cursor -= 1
            elif data == EC.enter:
                self.stash = None
                if self.lines:
                    if self.line != self.lines[-1]:
                        self.lines.append(self.line)
                else:
                    self.lines.append(self.line)
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
            if self.cursor < len(self.line):
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


class ConsoleReader:
    """Read key presses for console."""

    def __init__(self):
        """Save terminal state and init stdin."""
        self.fd = sys.stdin.fileno()
        self.old_attr = termios.tcgetattr(self.fd)
        tty.setraw(self.fd)

    async def start_connection(self, edit_line, process):
        """Connect protocol."""
        self.transport, self.protocol = \
            await asyncio.get_event_loop().connect_read_pipe(
                lambda: KeypressReaderProtocol(edit_line, process),
                sys.stdin)

    def __del__(self):
        """Reset the terminal."""
        termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old_attr)


class ConsoleWriter:
    """Writer to group logging and console text."""

    def __init__(self):
        """Init."""
        self.edit = None
        self.cursor = 0
        self.fd = sys.stdout.fileno()
        self.old_attr = termios.tcgetattr(self.fd)

    def write(self, data: bytes):
        """Stream writer, primarily for logging."""
        ln = EC.cr_clr + data + b'\r\n'
        if self.edit is not None:
            ln += EC.cr_clr + self.edit + EC.mv_left
            if self.cursor > 0:
                ln += b'\x1b[' + str(self.cursor).encode() + b'C'
        sys.stdout.buffer.write(ln)
        sys.stdout.flush()

    def edit_line(self, edit: bytes, cursor: int):
        """Update the edit line and cursor position."""
        self.edit = edit
        if self.edit is None:
            sys.stdout.buffer.write(b'\r\n')
            sys.stdout.flush()
            return
        self.cursor = cursor
        ln = EC.cr_clr + self.edit + EC.mv_left
        if self.cursor > 0:
            ln += b'\x1b[' + str(self.cursor).encode() + b'C'
        sys.stdout.buffer.write(ln)
        sys.stdout.flush()

    def __del__(self):
        """Reset the terminal."""
        termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old_attr)


class Console:
    """Provide a text console to interact with a Bus."""

    def __init__(self, bus_ip: str = '127.0.0.1', bus_port: int = 1324,
                 tag_info: dict = {}):
        """
        Connect to bus_ip:bus_port and provide console interaction with a Bus.

        Event loop must be running.
        """
        self.reader = ConsoleReader()
        self.writer = ConsoleWriter()
        logging.basicConfig(stream=self.writer)
        self.busclient = BusClient(bus_ip, bus_port, module='Console')
        self.tags: dict[str, Tag] = {}
        for tagname, tag in tag_info.items():
            tag_for_web(tagname, tag)
            self.tags[tagname] = Tag(tagname, tag['type'])
        self.quit = asyncio.Event()

    def write_tag(self, tag: Tag):
        """Append or insert tag value through writer."""
        ln = f'{tag.name} {tag.value}'.encode()
        self.writer.write(ln)

    def process(self, command: bytes):
        """Execute command."""
        cmd, var, val = (command.split(b' ') + [None] * 3)[:3]
        if var is not None:
            var = var.decode()
        if var is None:
            tagnames = self.tags.keys()
        else:
            tagnames = [x for x in self.tags.keys() if var in x]
        if cmd in [b'q', b'quit']:
            self.quit.set()  # does not close connection tidily
        elif cmd in [b'g', b'get']:
            for tagname in tagnames:
                self.write_tag(self.tags[tagname])
        elif cmd == b'set':
            pass
        elif cmd in [b's', b'sub']:
            for tagname in tagnames:
                self.tags[tagname].add_callback(self.write_tag)
                self.write_tag(self.tags[tagname])
        elif cmd in [b'u', b'unsub']:
            for tagname in tagnames:
                if self.write_tag in self.tags[tagname].pub:
                    self.tags[tagname].del_callback(self.write_tag)
        elif cmd in [b'l', b'list']:
            ln = ' '.join(tagnames).encode()
            self.writer.write(ln)
        elif cmd in [b'w', b'watch']:
            pass
        elif cmd in [b'h', b'help']:
            self.writer.write(
                b'list <match>              or l <match>\r\n'
                b'get <match>               or g <match>\r\n'
                b'set tagname value\r\n'
                b'sub <match>               or s <match>\r\n'
                b'unsub <match>             or u <match>\r\n'
                b'watch <systemd name>      or w <systemd name>\r\n'
                b'---------------------------------------------')

    async def start(self):
        """Start polling, does not return until finished."""
        await self.busclient.start()
        await self.reader.start_connection(self.writer.edit_line, self.process)
        await self.quit.wait()  # Idle wait until user quits the console
