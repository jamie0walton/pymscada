"""
Shared value tags.

Configured to NOT use asyncio.
bus_id is python id(), 0 is null pointer in c, 0 is local bus.
"""
import time
import array
import logging

TYPES = {
    'int': int,
    'str': str,
    'float': float,
    'list': list,
    'dict': dict,
    'bytes': bytes
}


def tag_for_web(tagname: str, tag: dict):
    """Correct tag dictionary in place to be suitable for web client."""
    tag['name'] = tagname
    tag['id'] = None
    if 'desc' not in tag:
        tag['desc'] = tag.name
    if 'multi' in tag:
        tag['type'] = 'int'
    else:
        if 'type' not in tag:
            tag['type'] = 'float'
        else:
            if tag['type'] not in TYPES:
                tag['type'] = 'str'
    if tag['type'] == 'int':
        tag['dp'] = 0
    elif tag['type'] == 'float' and 'dp' not in tag:
        tag['dp'] = 2
    elif tag['type'] == 'str' and 'dp' in tag:
        del tag['dp']


class UniqueTag(type):
    """Super Tag class only create unique tags for unique tag names."""

    __cache = {}
    __notify = None

    def __call__(cls, tagname: str, tagtype: type = None):
        """Each time a new tag is created, check if it is really new."""
        if tagname in cls.__cache:
            tag = cls.__cache[tagname]
            if tagtype is not None and tagtype is not tag.type:
                exit(f"{tagname} cannot be recast to {tagtype}")
        else:
            if tagtype is None:
                raise TypeError(f"{tagname} type is undefined.")
            tag = cls.__new__(cls, tagname, tagtype)
            tag.__init__(tagname, tagtype)
            tag.id = None
            cls.__cache[tagname] = tag
            if cls.__notify is not None:
                cls.__notify(tag)
        return tag

    def tagnames(cls) -> list[str]:
        """Return all tagnames of class Tag."""
        return cls.__cache.keys()

    def tags(cls) -> list:
        """Return all tags of class Tag."""
        return cls.__cache.values()

    def set_notify(cls, callback):
        """Set ONE routine to notify when new tags are added."""
        cls.__notify = callback

    def del_notify(cls):
        """Set ONE routine to notify when new tags are added."""
        cls.__notify = None

    def get_all_tags(cls) -> dict[str, 'Tag']:
        """Return all current tags as list[Tag]."""
        return cls.__cache


class Tag(metaclass=UniqueTag):
    """Tag provides consistent bus access, filtering and shard history."""

    __slots__ = ('__id', 'name', 'type', '__value', '__time_us', '__multi',
                 '__min', '__max', '__deadband', 'from_bus', '__age_us',
                 'times_us', 'values', 'pub', 'in_pub', 'pub_id', 'in_pub_id',
                 'desc', 'units', 'dp')

    def __init__(self, tagname: str, tagtype) -> None:
        """Initialise with a unique name and the data type."""
        self.__id = None
        self.name = tagname
        if type(tagtype) is type:
            self.type = tagtype
        else:
            self.type = TYPES[tagtype]
        self.__value = None
        self.__time_us: int = 0
        self.__multi = None
        self.__min = None
        self.__max = None
        self.__deadband = None
        self.from_bus = 0
        self.__age_us = None
        self.times_us = None
        self.values = None
        self.pub = {}
        self.in_pub = None
        self.pub_id = []
        self.in_pub_id = None
        self.desc = ''
        self.units = None
        self.dp = None

    def add_callback(self, callback, bus_id: int = 0):
        """Add a callback to update the value when a change is seen."""
        if not callable(callback):
            raise TypeError(f"{callback} must be callable.")
        self.pub[callback] = bus_id

    def del_callback(self, callback):
        """Remove the callback."""
        del self.pub[callback]

    def add_callback_id(self, callback):
        """Add a callback for when a process needs to know the id is live."""
        if not callable(callback):
            raise TypeError(f"{callback} must be callable.")
        if callback not in self.pub_id:
            self.pub_id.append(callback)

    def del_callback_id(self, callback):
        """Remove the callback."""
        if callback in self.pub_id:
            self.pub_id.remove(callback)

    def store(self):
        """Store history in an array.array."""
        self.times_us.append(self.time_us)
        self.values.append(self.value)
        oldest = self.time_us - self.age_us
        for _i, t in enumerate(self.times_us):
            if t >= oldest:
                return
        del self.times_us[:_i]
        del self.values[:_i]

    def get(self, time_us: int):
        """Return everything newer."""
        if self.times_us is None:
            return self.__value
        for i in range(len(self.times_us) - 1, -1, -1):
            # equal is right as queries are for the most recent
            # matching time.
            if self.times_us[i] <= time_us:
                return self.values[i]
        return self.values[0]

    @property
    def value(self):
        """Get current value."""
        return self.__value

    @value.setter
    def value(self, value) -> None:
        """Set value, filter and store history. Won't force type."""
        if self.in_pub is not None:
            logging.critical(f"{self.name} attempt to set while __in_pub")
            return
        # handle value if tuple with time_us and maybe from_bus
        if type(value) is tuple:
            if len(value) == 3:
                value, time_us, from_bus = value
            else:  # must be len(value) == 2
                value, time_us = value
                from_bus = 0
        else:
            time_us = int(time.time() * 1e6)
            from_bus = 0
        if type(value) is int and self.type is float:
            value = float(value)
        elif type(value) is float and self.type is int:
            logging.warning(f"{self.name} coercing float to int")
            value = int(value)
        if type(value) is self.type:
            deadband = self.__deadband
            if self.__min is not None and value <= self.__min:
                value = self.__min
                if deadband is not None:
                    deadband = 0.0  # ignore deadband at limit
            if self.__max is not None and value >= self.__max:
                value = self.__max
                if deadband is not None:
                    deadband = 0.0  # ignore deadband at limit
            # This has implications for what 'old data' might mean
            if deadband is None or self.__value is None or \
                    abs(self.__value - value) > deadband:
                self.__value = value
                self.time_us = time_us
                self.from_bus = from_bus
                if self.__age_us is not None:
                    self.store()
                # only publish for > deadband change
                for self.in_pub, bus_id in self.pub.items():
                    if from_bus != bus_id:
                        self.in_pub(self)
                self.in_pub = None
        else:
            raise TypeError(f"{self.name} won't force {type(value)} "
                            f"to {self.type}")

    @property
    def id(self):
        """Get current id."""
        return self.__id

    @id.setter
    def id(self, id) -> None:
        """Set id and callback if registered."""
        if self.in_pub_id is not None:
            logging.critical(f"{self.name} attempt to set id in a callback")
            return
        self.__id = id
        for self.in_pub_id in self.pub_id:
            self.in_pub_id(self)
        self.in_pub_id = None

    @property
    def time_us(self) -> int:
        """Return the time in us."""
        return self.__time_us

    @time_us.setter
    def time_us(self, time_us: int):
        """Make sure this is int, should _always_ be. TODO remove."""
        if type(time_us) is not int:
            logging.warning(f"{self.name} time_us was not an int, FIX.")
            self.__time_us = int(time_us)
        else:
            self.__time_us = time_us

    @property
    def value_min(self):
        """Return minimum for tag value."""
        return self.__min

    @value_min.setter
    def value_min(self, minimum) -> None:
        """Set minimum, type matching enforced."""
        self.__min = self.type(minimum)

    @property
    def value_max(self):
        """Return maximum for tag value."""
        return self.__max

    @value_max.setter
    def value_max(self, maximum) -> None:
        """Set maximum, type matching enforced."""
        self.__max = self.type(maximum)

    @property
    def multi(self) -> int:
        """Return the number order from the list."""
        return self.__multi

    @multi.setter
    def multi(self, multi: list[str]) -> None:
        """Set multi list of states."""
        if self.type is not int:
            raise TypeError(f"{self.name} multi but value not int")
        if type(multi) is not list:
            raise TypeError(f"{self.name} multi must be list")
        self.__multi = multi
        self.__min = 0
        self.__max = len(multi) - 1

    @property
    def deadband(self):
        """Return deadband."""
        return self.__deadband

    @deadband.setter
    def deadband(self, deadband):
        if self.type in [int, float, None]:
            self.__deadband = deadband
        else:
            raise TypeError(f"deadband invalid {self.name} not int, float")

    @property
    def age_us(self):
        """Return deadband."""
        return self.__age_us

    @age_us.setter
    def age_us(self, age_us: int):
        """Set age for history, clobbers old history when set."""
        if self.type in [int, float]:
            self.__age_us = age_us
            self.times_us = array.array('Q')
            if self.type is int:
                self.values = array.array('q')
            elif self.type is float:
                self.values = array.array('d')
        else:
            raise TypeError(f"shard invalid {self.name} not int, float")
