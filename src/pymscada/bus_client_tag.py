"""
Bus client tags with lint-friendly types.

bus_id is python id(), 0 is null pointer in c, 0 is local bus.
"""
import array
from collections.abc import Callable
import json
import logging
import struct
import time
import pymscada.protocol_constants as pc

SLOTS = ('_id', 'name', '_value', '_min', '_max', '_deadband', '_multi',
         'time_us', '_age_us', 'times_us', 'values', 'desc', 'units', 'dp', 
         'from_bus', 'pub', 'in_pub', 'pub_id', 'in_pub_id', 'type')


class UniqueTagTyped(type):
    """Ensure singleton by tag name and provide class methods."""

    __cache: dict[str, 'TagTyped'] = {}
    __bus_callback: Callable | None = None

    def __call__(cls, tagname: str):
        """Each time a new tag is created, check if it is really new."""
        if cls.__bus_callback is None:
            raise SystemExit("TagTyped requires BusClient.")
        if tagname in cls.__cache:
            existing = cls.__cache[tagname]
            if type(existing) is not cls:
                raise SystemExit(
                    f"{tagname} already exists as {type(existing).__name__}, "
                    f"cannot create as {cls.__name__}"
                )
            return existing
        tag: TagTyped = super().__call__(tagname)
        tag.id = None
        cls.__cache[tagname] = tag
        cls.__bus_callback(tag)
        return tag

    @classmethod
    def set_bus_callback(cls, callback: Callable):
        """Set callback for tag notification. Called by BusClient."""
        cls.__bus_callback = callback

    @classmethod
    def del_bus_callback(cls):
        """Only use as a finalizer. Called by BusClient."""
        cls.__bus_callback = None

    @classmethod
    def check_none_values(cls, tagnames: list[str]) -> list[str]:
        """Return list of tagnames that are None."""
        result = []
        for tagname in tagnames:
            if tagname in cls.__cache:
                tag = cls.__cache[tagname]
                if tag._value is None:
                    result.append(tagname)
        return result


class TagTyped(metaclass=UniqueTagTyped):
    """Base class providing standard instance methods and properties."""

    __slots__ = SLOTS

    def __init__(self, tagname: str) -> None:
        """Initialise with a unique name."""
        self._id: int | None = None
        self.name: str = tagname
        self._value = None
        self.time_us: int = 0
        self.from_bus: int = 0
        self.pub = {}
        self.in_pub: Callable | None = None
        self.pub_id = []
        self.in_pub_id: Callable | None = None
        self.desc = ''
        self.units = None
        self.dp = None
        self.type: type = type(None)

    def add_callback(self, callback: Callable, bus_id: int = 0):
        """Add a callback to update the value when a change is seen."""
        self.pub[callback] = bus_id

    def del_callback(self, callback: Callable):
        """Remove the callback."""
        del self.pub[callback]

    def add_callback_id(self, callback: Callable):
        """Add a callback for when a process needs to know the id is live."""
        if callback not in self.pub_id:
            self.pub_id.append(callback)

    def del_callback_id(self, callback: Callable):
        """Remove the callback."""
        if callback in self.pub_id:
            self.pub_id.remove(callback)

    @property
    def is_none(self) -> bool:
        """Check if value is None."""
        return self._value is None

    def set_value(self, value, time_us: int, bus: int | None = None):
        """Set value with time_us and bus_id. Base implementation."""
        if self.in_pub is not None:
            raise SystemError(f"{self.name} attempt to set while __in_pub")
        if bus is None:
            bus = 0
        self._value = value
        self.time_us = time_us
        self.from_bus = bus
        for self.in_pub, bus_id in self.pub.items():
            if bus != bus_id:
                try:
                    self.in_pub(self)
                except Exception as e:
                    raise SystemError(f'{self.name} {value} publish {e}')
        self.in_pub = None

    @property
    def id(self) -> int | None:
        """Get current id."""
        return self._id

    @id.setter
    def id(self, id: int) -> None:
        """Set id and callback if registered."""
        if self.in_pub_id is not None:
            raise SystemError(f"{self.name} attempt to set id in a callback")
        self._id = id
        for self.in_pub_id in self.pub_id:
            self.in_pub_id(self)
        self.in_pub_id = None


class TagInt(TagTyped):
    """Integer bus tag."""

    __slots__ = SLOTS

    def __init__(self, tagname: str):
        """Initialise with a unique name."""
        super().__init__(tagname)
        self.type: type = int
        self._min: int | None = None
        self._max: int | None = None
        self._deadband: int | None = None
        self._multi: list[str] | None = None
        self._age_us: int = -1
        self.times_us: array.array[int] = array.array('Q')
        self.values: array.array[int] = array.array('q')

    @property
    def value(self) -> int:
        """Get current int value."""
        if self._value is None:
            raise SystemExit(f"{self.name} value accessed before initialization")
        return self._value

    @value.setter
    def value(self, value: int):
        """Set int value."""
        self.set_value(value, int(time.time() * 1e6), 0)

    def set_value(self, value: int, time_us: int, bus: int | None = None):
        """Set int value with time_us and bus_id."""
        deadband = self._deadband
        if self._min is not None and value <= self._min:
            value = self._min
            if deadband is not None:
                deadband = 0
        if self._max is not None and value >= self._max:
            value = self._max
            if deadband is not None:
                deadband = 0
        if deadband is None or self._value is None or \
                abs(self._value - value) > deadband:
            super().set_value(value, time_us, bus)
            if self._age_us >= 0:
                self.store()

    def store(self):
        """Store history in an array.array."""
        self.times_us.append(self.time_us)
        self.values.append(self.value)
        oldest = self.time_us - self._age_us
        i = 0
        for i, t in enumerate(self.times_us):
            if t >= oldest:
                break
        del self.times_us[:i]
        del self.values[:i]

    def get(self, time_us: int):
        """Return everything newer."""
        if len(self.times_us) == 0:
            return self._value
        for i in range(len(self.times_us) - 1, -1, -1):
            if self.times_us[i] <= time_us:
                return self.values[i]
        return self.values[0]

    @property
    def value_min(self) -> int | None:
        """Return minimum for tag value."""
        return self._min

    @value_min.setter
    def value_min(self, minimum: int):
        """Set minimum, type matching enforced."""
        self._min = int(minimum)

    @property
    def value_max(self) -> int | None:
        """Return maximum for tag value."""
        return self._max

    @value_max.setter
    def value_max(self, maximum: int) -> None:
        """Set maximum, type matching enforced."""
        self._max = int(maximum)

    @property
    def deadband(self) -> int | None:
        """Return deadband."""
        return self._deadband

    @deadband.setter
    def deadband(self, deadband: int):
        """Set deadband."""
        self._deadband = int(deadband)

    @property
    def age_us(self) -> int | None:
        """Return age_us."""
        if self._age_us < 0:
            return None
        return self._age_us

    @age_us.setter
    def age_us(self, age_us: int):
        """Set age for history, clobbers old history when set."""
        if self._age_us < 0:
            self.times_us.append(self.time_us)
            self.values.append(self.value)
        self._age_us = age_us

    @property
    def multi(self) -> list[str] | None:
        """Return the list of states."""
        return self._multi

    @multi.setter
    def multi(self, multi: list[str]) -> None:
        """Set multi list of states."""
        self._multi = multi
        self._min = 0
        self._max = len(multi) - 1

    @property
    def packed_value(self) -> bytes:
        """Return packed int value for bus protocol."""
        return struct.pack('!Bq', pc.TYPE.INT, self.value)

    def set_packed_value(self, value: bytes, time_us: int, bus: int):
        """Unpack packed int value and set it."""
        data_type = struct.unpack_from('!B', value, offset=0)[0]
        if data_type != pc.TYPE.INT:
            raise TypeError(f'{self.name} expected INT, got {data_type}')
        data = struct.unpack_from('!q', value, offset=1)[0]
        self.set_value(data, time_us, bus)


class TagFloat(TagTyped):
    """Float bus tag."""

    __slots__ = SLOTS

    def __init__(self, tagname: str):
        """Initialise with a unique name."""
        super().__init__(tagname)
        self.type: type = float
        self._min: float | None = None
        self._max: float | None = None
        self._deadband: float | None = None
        self._age_us: int = -1
        self.times_us: array.array[int] = array.array('Q')
        self.values: array.array[float] = array.array('d')

    @property
    def value(self) -> float:
        """Get current float value."""
        if self._value is None:
            raise SystemExit(f"{self.name} value accessed before initialization")
        return self._value

    @value.setter
    def value(self, value: float):
        """Set float value."""
        self.set_value(value, int(time.time() * 1e6), 0)

    def set_value(self, value: float, time_us: int, bus: int | None = None):
        """Set float value with time_us and bus_id."""
        deadband = self._deadband
        if self._min is not None and value <= self._min:
            value = self._min
            if deadband is not None:
                deadband = 0.0
        if self._max is not None and value >= self._max:
            value = self._max
            if deadband is not None:
                deadband = 0.0
        if deadband is None or self._value is None or \
                abs(self._value - value) > deadband:
            super().set_value(value, time_us, bus)
            if self._age_us >= 0:
                self.store()

    def store(self):
        """Store history in an array.array."""
        self.times_us.append(self.time_us)
        self.values.append(self.value)
        oldest = self.time_us - self._age_us
        i = 0
        for i, t in enumerate(self.times_us):
            if t >= oldest:
                break
        del self.times_us[:i]
        del self.values[:i]

    def get(self, time_us: int):
        """Return everything newer."""
        if len(self.times_us) == 0:
            return self._value
        for i in range(len(self.times_us) - 1, -1, -1):
            if self.times_us[i] <= time_us:
                return self.values[i]
        return self.values[0]

    @property
    def value_min(self) -> float | None:
        """Return minimum for tag value."""
        return self._min

    @value_min.setter
    def value_min(self, minimum: float):
        """Set minimum, type matching enforced."""
        self._min = float(minimum)

    @property
    def value_max(self) -> float | None:
        """Return maximum for tag value."""
        return self._max

    @value_max.setter
    def value_max(self, maximum: float):
        """Set maximum, type matching enforced."""
        self._max = float(maximum)

    @property
    def deadband(self) -> float | None:
        """Return deadband."""
        return self._deadband

    @deadband.setter
    def deadband(self, deadband: float):
        """Set deadband."""
        self._deadband = float(deadband)

    @property
    def age_us(self) -> int | None:
        """Return age_us."""
        if self._age_us < 0:
            return None
        return self._age_us

    @age_us.setter
    def age_us(self, age_us: int):
        """Set age for history, clobbers old history when set."""
        if self._age_us < 0:
            self.times_us.append(self.time_us)
            self.values.append(self.value)
        self._age_us = age_us

    @property
    def packed_value(self) -> bytes:
        """Return packed float value for bus protocol."""
        return struct.pack('!Bd', pc.TYPE.FLOAT, self.value)

    def set_packed_value(self, value: bytes, time_us: int, bus: int):
        """Unpack packed float value and set it."""
        data_type = struct.unpack_from('!B', value, offset=0)[0]
        if data_type != pc.TYPE.FLOAT:
            raise TypeError(f'{self.name} expected FLOAT, got {data_type}')
        data = struct.unpack_from('!d', value, offset=1)[0]
        self.set_value(data, time_us, bus)


class TagStr(TagTyped):
    """String bus tag."""

    __slots__ = SLOTS

    def __init__(self, tagname: str):
        """Initialise with a unique name."""
        super().__init__(tagname)
        self.type = str

    @property
    def value(self) -> str:
        """Get current string value."""
        if self._value is None:
            raise SystemExit(f"{self.name} value accessed before initialization")
        return self._value

    @value.setter
    def value(self, value: str):
        """Set string value."""
        self.set_value(value, int(time.time() * 1e6), 0)

    @property
    def packed_value(self) -> bytes:
        """Return packed string value for bus protocol."""
        size = len(self.value)
        return struct.pack(f'!B{size}s', pc.TYPE.STR, self.value.encode())

    def set_packed_value(self, value: bytes, time_us: int, bus: int):
        """Unpack packed string value and set it."""
        data_type = struct.unpack_from('!B', value, offset=0)[0]
        if data_type != pc.TYPE.STR:
            raise TypeError(f'{self.name} expected STR, got {data_type}')
        data = struct.unpack_from(f'!{len(value) - 1}s', value,
                                   offset=1)[0].decode()
        self.set_value(data, time_us, bus)


class TagBytes(TagTyped):
    """Bytes bus tag."""

    __slots__ = SLOTS

    def __init__(self, tagname: str):
        """Initialise with a unique name."""
        super().__init__(tagname)
        self.type = bytes

    @property
    def value(self) -> bytes:
        """Get current bytes value."""
        if self._value is None:
            raise SystemExit(f"{self.name} value accessed before initialization")
        return self._value

    @value.setter
    def value(self, value: bytes):
        """Set bytes value."""
        self.set_value(value, int(time.time() * 1e6), 0)

    @property
    def packed_value(self) -> bytes:
        """Return packed bytes value for bus protocol."""
        size = len(self.value)
        return struct.pack(f'!B{size}s', pc.TYPE.BYTES, self.value)

    def set_packed_value(self, value: bytes, time_us: int, bus: int):
        """Unpack packed bytes value and set it."""
        data_type = struct.unpack_from('!B', value, offset=0)[0]
        if data_type != pc.TYPE.BYTES:
            raise TypeError(f'{self.name} expected BYTES, got {data_type}')
        data = struct.unpack_from(f'!{len(value) - 1}s', value,
                                   offset=1)[0]
        self.set_value(data, time_us, bus)


class TagList(TagTyped):
    """List bus tag."""

    __slots__ = SLOTS

    def __init__(self, tagname: str):
        """Initialise with a unique name."""
        super().__init__(tagname)
        self.type = list

    @property
    def value(self) -> list:
        """Get current list value."""
        if self._value is None:
            raise SystemExit(f"{self.name} value accessed before initialization")
        return self._value

    @value.setter
    def value(self, value: list):
        """Set list value."""
        self.set_value(value, int(time.time() * 1e6), 0)

    @property
    def packed_value(self) -> bytes:
        """Return packed list value for bus protocol."""
        jsonstr = json.dumps(self.value).encode()
        size = len(jsonstr)
        return struct.pack(f'!B{size}s', pc.TYPE.JSON, jsonstr)

    def set_packed_value(self, value: bytes, time_us: int, bus: int):
        """Unpack packed list value and set it."""
        data_type = struct.unpack_from('!B', value, offset=0)[0]
        if data_type != pc.TYPE.JSON:
            raise TypeError(f'{self.name} expected JSON, got {data_type}')
        data = json.loads(struct.unpack_from(f'!{len(value) - 1}s',
                                              value, offset=1
                                              )[0].decode())
        self.set_value(data, time_us, bus)


class TagDict(TagTyped):
    """Dict bus tag."""

    __slots__ = SLOTS

    def __init__(self, tagname: str):
        """Initialise with a unique name."""
        super().__init__(tagname)
        self.type = dict

    @property
    def value(self) -> dict:
        """Get current dict value."""
        if self._value is None:
            raise SystemExit(f"{self.name} value accessed before initialization")
        return self._value

    @value.setter
    def value(self, value: dict):
        """Set dict value."""
        self.set_value(value, int(time.time() * 1e6), 0)

    @property
    def packed_value(self) -> bytes:
        """Return packed dict value for bus protocol."""
        jsonstr = json.dumps(self.value).encode()
        size = len(jsonstr)
        return struct.pack(f'!B{size}s', pc.TYPE.JSON, jsonstr)

    def set_packed_value(self, value: bytes, time_us: int, bus: int):
        """Unpack packed dict value and set it."""
        data_type = struct.unpack_from('!B', value, offset=0)[0]
        if data_type != pc.TYPE.JSON:
            raise TypeError(f'{self.name} expected JSON, got {data_type}')
        data = json.loads(struct.unpack_from(f'!{len(value) - 1}s',
                                              value, offset=1
                                              )[0].decode())
        self.set_value(data, time_us, bus)
