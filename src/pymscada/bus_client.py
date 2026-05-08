"""Bus client."""
import asyncio
from collections.abc import Callable
import struct
import json
import time
import logging
from struct import unpack
from pymscada.tag import Tag
from pymscada.bus_client_tag import TagTyped, TagBytes
import pymscada.protocol_constants as pc

PROTOCOL_VERSION = 1


class BusTask:
    """Create a Task; on fatal failure optionally log then exit the process."""

    def __init__(self, coroutine, *, ignore_cancelled: bool = True,
                 fatal: bool = True):
        self._ignore_cancelled = ignore_cancelled
        self._fatal = fatal
        self.task = asyncio.create_task(coroutine)
        self.task.add_done_callback(self.done)

    def done(self, task: asyncio.Task):
        if task.cancelled():
            if self._ignore_cancelled:
                return
        exc = task.exception()
        if exc is not None:
            if self._fatal:
                raise SystemExit(exc)


class BusClient:
    """
    Connects to a Bus Server.

    The client is created without a connection. client.start() creates the
    connection and checks the tags at that time. When the connection fails
    the client dies. A connection is mandatory for the client to run.
    """

    def __init__(self, ip: str | None = '127.0.0.1', port: int | None = 1324,
                 tag_info=None, module: str = '_unset_'):
        """Create bus server."""
        self.ip = ip
        self.port = port
        self.tag_info = tag_info
        self.module = module
        self.reader = None
        self.writer = None
        self.to_get_id: dict[str, Tag | TagTyped] = {}
        self.to_publish: dict[str, Tag | TagTyped] = {}
        self.tag_by_id: dict[int, Tag | TagTyped] = {}
        self.tag_by_name: dict[str, Tag | TagTyped] = {}
        self.rta_handlers: dict[str, Callable] = {}
        self.pending = {}
        TagTyped.set_bus_callback(self.add_tag)
        self.history_tag: TagBytes | None = None

    def publish(self, tag: Tag | TagTyped):
        """
        Update bus server with tag value change.

        A tag is given bus_id id(self) when set from bus. Don't publish to
        source.
        """
        if tag.id is None:
            self.to_publish[tag.name] = tag
            return
        data = tag.packed_value
        self.write(pc.COMMAND.SET, tag.id, tag.time_us, data)

    def add_callback_rta(self, tagname, handler: Callable):
        """Collect callback handlers."""
        self.rta_handlers[tagname] = handler

    def rta(self, tagname: str, request: dict):
        """Send a Request Set message."""
        time_us = int(time.time() * 1e6)
        jsonstr = json.dumps(request).encode()
        size = len(jsonstr)
        data = struct.pack(f'>B{size}s', pc.TYPE.JSON, jsonstr)
        tag_id = self.tag_by_name[tagname].id
        if tag_id is None:
            raise ValueError(f'tag {tagname} has no id')
        self.write(pc.COMMAND.RTA, tag_id, time_us, data)

    def write(self, command: pc.COMMAND, tag_id: int, time_us: int,
              data: bytes):
        """Write a message."""
        if self.writer is None:
            return
        size_total = len(data)
        logging.debug(f'{self.module}: write cmd={command} tag_id={tag_id} '
                     f'size_total={size_total}')
        for i in range(0, len(data) + 1, pc.MAX_LEN):
            snip = data[i:i+pc.MAX_LEN]
            size = len(snip)
            msg = struct.pack(f">BBHHQ{size}s", PROTOCOL_VERSION, command,
                              tag_id, size, time_us, snip)
            try:
                self.writer.write(msg)
            except Exception as e:
                logging.error(f'{self.module}: write {e}  cmd={command} '
                              f'tag_id={tag_id} size={size}')

    def add_tag(self, tag: Tag | TagTyped):
        """Add the new tag and get the tag's bus ID."""
        tag.add_callback(self.publish, id(self))
        self.tag_by_name[tag.name] = tag
        self.to_get_id[tag.name] = tag
        if not tag.is_none:
            self.to_publish[tag.name] = tag
        if self.ip is None or self.port is None:
            return
        if self.writer is None:
            self.to_get_id[tag.name] = tag
            return
        self.write(pc.COMMAND.ID, 0, 0, tag.name.encode())

    async def open_connection(self):
        """Establish connection and callbacks."""
        self.reader, self.writer = await asyncio.open_connection(
            self.ip, self.port)
        self.addr = self.writer.get_extra_info('sockname')
        self.write(pc.COMMAND.LOG, 0, 0, f'{self.module} connected'.encode())
        for tag in self.to_get_id.values():
            self.write(pc.COMMAND.ID, 0, 0, tag.name.encode())
        self.to_get_id = {}
        logging.warning(f'connected {self.addr} {self.port}')
        for tag in Tag.get_all_tags().values():
            self.add_tag(tag)
        Tag.set_notify(self.add_tag)

    async def close_connection(self):
        """Close connection and remove callbacks."""
        logging.warning(f'closed/ing connection {self.addr}')
        Tag.del_notify()
        for tag in self.tag_by_name.values():
            tag.del_callback(self.publish)
        if self.writer is None:
            return
        self.writer.close()  # writer owns the socket
        await self.writer.wait_closed()

    async def read(self):
        """Read forever."""
        while self.reader is not None:
            try:
                head = await self.reader.readexactly(14)
            except Exception as e:
                logging.warning(f'{self.module}: read error {e}')
                break
            version, cmd, tag_id, size, time_us = struct.unpack('>BBHHQ', head)
            if version != PROTOCOL_VERSION:
                logging.critical(f'bad version or misaligned {head.decode()}')
                raise SystemExit('Protocol Error')
            if size == 0:
                self.process(cmd, tag_id, time_us, None)
                continue
            try:
                payload = await self.reader.readexactly(size)
            except Exception as e:
                logging.warning(f'{self.module}: read payload error {e}')
                break
            data = struct.unpack(f'>{size}s', payload)[0]
            # if MAX_LEN then a continuation packet is required
            # if not MAX_LEN then this is the final or only packet
            if tag_id in self.pending:
                if size == pc.MAX_LEN:
                    self.pending[tag_id] += data
                    continue
                else:
                    data = self.pending[tag_id] + data
                    del self.pending[tag_id]
            elif size == pc.MAX_LEN:
                self.pending[tag_id] = data
                continue
            self.process(cmd, tag_id, time_us, data)
        await self.close_connection()

    def process(self, cmd, tag_id, time_us, value):
        """Process bus message, updating the local tag value."""
        if cmd == pc.COMMAND.ERR:
            logging.warning(f'Bus server error {tag_id} '
                            f'{pc.COMMAND.text(cmd)} {value}')
            return
        if cmd == pc.COMMAND.ID:
            tag = self.tag_by_name[value.decode()]
            tag.id = tag_id
            self.tag_by_id[tag_id] = tag
            self.write(pc.COMMAND.SUB, tag.id, 0, b'')
            if tag.name in self.tag_by_name:
                self.tag_by_id[tag_id] = tag
            if tag.name in self.to_publish:
                self.publish(tag)
                del self.to_publish[tag.name]
            return
        tag = self.tag_by_id[tag_id]
        if cmd == pc.COMMAND.SET:
            if value is None:
                try:
                    if self.tag_info is None:
                        return
                    data = self.tag_info[tag.name]['init']
                    time_us = int(time.time() * 1e6)
                    bus_id = None  # needed to pub to connected webclients
                    tag.set_value(data, time_us, bus_id)
                    logging.warning(f'{tag.name} init value {data}')
                except KeyError:
                    pass
                return
            tag.set_packed_value(value, time_us, id(self))
        elif cmd == pc.COMMAND.RTA:
            data = struct.unpack_from(f'!{len(value) - 1}s', value, offset=1
                                      )[0].decode()
            data = json.loads(data)
            logging.info(f'{self.module}: RTA received {tag.name} {data} '
                         f'from tag_id {tag_id}')
            try:
                self.rta_handlers[tag.name](data)
            except KeyError:
                logging.warning(f'{self.module}: unhandled RTA for {tag.name} {data}')
        else:
            raise SystemExit(f'Invalid message {cmd}')

    async def shutdown(self):
        """Shutdown starts with closing the writer."""
        if self.writer is None:
            return
        self.writer.close()
        await self.writer.wait_closed()
        TagTyped.del_bus_callback()

    async def start(self):
        """Start async."""
        if self.ip is None or self.port is None:
            logging.warning('busclient in pytest mode, no ip or port')
            return
        await self.open_connection()
        BusTask(self.read())

    def read_done(self, task: asyncio.Task):
        """Read task done."""
        if task.cancelled():
            return
        exc = task.exception()
        if exc:
            logging.error("read task failed", exc_info=exc)
            raise SystemExit(1) from exc

    async def get_history(self):
        """Get history."""
        if self.history_tag is None:
            return
        age_us_tags = {}
        for tag in self.tag_by_name.values():
            if tag.age_us is not None:
                age_us_tags[tag.name] = tag
        if len(age_us_tags) == 0:
            return
        await asyncio.sleep(1.0)
        for tag in age_us_tags.values():
            if tag.id is None:
                raise ValueError(f"tag {tag.name} has no id")
        fill_done = asyncio.Event()
        fill_tags = set()

        def fill_history_cb(tag: TagBytes):
            # packed with self.rta.value = pack('>HHH', rta_id, tagid,
            # packtype) + data
            if len(tag.value) == 6:
                return
            _, tagid, packtype = unpack('>HHH', tag.value[:6])
            dtag = None
            for dtag in age_us_tags.values():
                if dtag.id == tagid:
                    break
            if dtag is None:
                logging.error(f"tag {tagid} not found")
                return
            payload = tag.value[6:]
            if packtype == 1:
                fmt = '>Qq'
            elif packtype == 2:
                fmt = '>Qd'
            else:
                logging.error(f"unknown packtype: {packtype}")
                return
            data = [unpack(fmt, payload[i:i+16])
                    for i in range(0, len(payload), 16)]
            repack_data = {}
            for time_us, value in data:
                repack_data[time_us] = value
            for time_us, value in repack_data.items():
                dtag.times_us.append(time_us)
                dtag.values.append(value)
            logging.info(f"{dtag.name} len {len(data)}->{len(repack_data)} "
                         f" {data[0]} {data[-1]} ")
            fill_tags.remove(dtag.name)
            if len(fill_tags):
                return
            fill_done.set()

        self.history_tag.add_callback(fill_history_cb)
        now = int(time.time() * 1000000)
        for tag in age_us_tags.values():
            start_us = now - tag.age_us
            request = {
                '__rta_id__': 0,
                'tagname': tag.name,
                'start_us': start_us,
                'end_us': now
            }
            logging.info(f"history {request}")
            self.rta(self.history_tag.name, request)
            fill_tags.add(tag.name)
        await fill_done.wait()
        self.history_tag.del_callback(fill_history_cb)
