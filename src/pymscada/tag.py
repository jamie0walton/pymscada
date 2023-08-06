"""Shared value tags."""
import time
import array
import logging

TYPES = {
    'int': int,
    'str': str,
    'float': float,
    'list': list,
    'dict': dict
}


def validate_tag(tag: dict):
    """Correct tag dictionary in place."""
    if 'desc' not in tag:
        logging.error(f"{tag} missing desc")
    if 'multi' in tag:
        if 'type' in tag:
            logging.warning(f"{tag} redundant type cast for multi")
        tag['type'] = int
    else:
        if 'type' not in tag:
            tag['type'] = float
        else:
            try:
                tag['type'] = TYPES[tag['type']]
            except KeyError:
                logging.error(f"{tag} invalid type {tag['type']}")
    if tag['type'] is int:
        if 'dp' in tag:
            logging.warning(f"{tag} redundant dp for int")
        tag['dp'] = 0
    elif tag['type'] is float and 'dp' not in tag:
        tag['dp'] = 2
    elif tag['type'] is str and 'dp' in tag:
        logging.warning(f"{tag} str cannot use dp")
        del tag['dp']


class UniqueTag(type):
    """Super Tag class only create unique tags for unique tag names."""

    __cache = {}
    notify = None

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
            if cls.notify is not None:
                cls.notify(tag)
        return tag

    def tagnames(cls) -> list[str]:
        """Return all tagnames of class Tag."""
        return cls.__cache.keys()

    def tags(cls) -> list:
        """Return all tags of class Tag."""
        return cls.__cache.values()

    def get_all_tags(cls) -> dict[str, 'Tag']:
        """Return all current tags as list[Tag]."""
        return cls.__cache


class Tag(metaclass=UniqueTag):
    """Tag provides consistent bus access, filtering and shard history."""

    __slots__ = ('id', 'name', 'type', '__value', '__time_us', '__multi',
                 '__min', '__max', '__deadband', 'from_bus', '__age_us',
                 'times_us', 'values', '__pub', '__in_pub', 'desc',
                 'units', 'dp')

    def __init__(self, tagname: str, tagtype) -> None:
        """Initialise with a unique name and the data type."""
        self.id = None
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
        self.__pub = []
        self.__in_pub = None
        self.desc = ''
        self.units = None
        self.dp = None

    def add_callback(self, callback):
        """Add a callback to update the value when a change is seen."""
        if not callable(callback):
            raise TypeError(f"{callback} must be callable.")
        if callback not in self.__pub:
            self.__pub.append(callback)

    def del_callback(self, callback):
        """Remove the callback, keep close with add_callback."""
        if callback in self.__pub:
            self.__pub.remove(callback)

    def del_all_callbacks(self):
        """TODO fix this use by businit."""
        self.__pub = []

    @property
    def value(self):
        """Get current value."""
        return self.__value

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

    @value.setter
    def value(self, value) -> None:
        """Set value, filter and store history. Won't force type."""
        if self.__in_pub is not None:
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
        if time_us == 0:
            return
        if type(value) is int and self.type is float:
            # logging.warning(f"{self.name} coercing int to float")
            value = float(value)
        elif type(value) is float and self.type is int:
            logging.warning(f"{self.name} coercing float to int")
            value = int(value)
        # elif value is None and self.type is str:
        #     logging.info(f"{self.name} setting empty string")
        #     value = ''
        # value, time_us and from_bus are now all scalars
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
                for self.__in_pub in self.__pub:  # noqa:B020
                    self.__in_pub(self)  # callback with self(Tag)
                self.__in_pub = None
        # elif value is None:
        #     logging.info(f"{self.name} got None from bus")
        else:
            raise TypeError(f"{self.name} won't force {type(value)} "
                            f"to {self.type}")

    @property
    def time_us(self) -> int:
        """Return the time in us."""
        return self.__time_us

    @time_us.setter
    def time_us(self, time_us: int):
        """Make sure this is int, should _always_ be. TODO remove."""
        if type(time_us) is not int:
            logging.warning(f"{self.name} was not an int, FIX.")
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
        if self.type != int:
            raise TypeError(f"{self.name} multi but value not int")
        if type(multi) != list:
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
            self.times_us = array.array('L')
            if self.type is int:
                self.values = array.array('i')
            elif self.type is float:
                self.values = array.array('f')
        else:
            raise TypeError(f"shard invalid {self.name} not int, float")
