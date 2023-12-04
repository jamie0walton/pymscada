"""Sampling utilities."""
from pathlib import Path
import shutil
from pymscada.tag import Tag


CPU_TEMP = False
if Path('/sys/class/thermal/thermal_zone0/temp').is_file():
    CPU_TEMP = True
with open('/proc/stat', 'r') as f:
    cpu_load = [int(x) for x in f.readline().split(None)[1:]]


def get_cpu_temp() -> float:
    """Return the CPU temp in °C."""
    temp = 0.
    if not CPU_TEMP:
        return temp
    with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
        temp = int(f.read()) / 1000
    return temp


def get_cpu_load() -> float:
    """Return cpu load in %."""
    global cpu_load
    old_cpu_load = cpu_load
    with open('/proc/stat', 'r') as f:
        cpu_load = [int(x) for x in f.readline().split(None)[1:]]
    idle = cpu_load[3] - old_cpu_load[3]
    used = sum(cpu_load) - sum(old_cpu_load)
    if used == 0:
        return 0
    return 100 * (used - idle) / used


def get_disk_use() -> float:
    """Return disk usage in %."""
    stat = shutil.disk_usage(Path('/'))
    return 100 * stat.used / stat.total


class Ping():
    """Async ping class."""

    def __init__(self, map: dict[str: Tag]) -> None:
        """Ping map, key as IP address, time placed into Tag.value."""
        self.map = map

    def step(self):
        """Step."""
        pass


class Ramp():
    """Ramp a value."""

    def __init__(self, ramp_tag: Tag, setpoint_tag: Tag, ramp=1) -> None:
        """Ramp."""
        self.ramp_tag = ramp_tag
        self.setpoint_tag = setpoint_tag
        self.ramp = ramp

    def step(self) -> None:
        """Step."""
        if self.setpoint_tag.value is None:
            return
        if self.ramp_tag.value is None:
            self.ramp_tag.value = self.setpoint_tag.value
            return
        if self.setpoint_tag.value > self.ramp_tag.value:
            self.ramp_tag.value = min(self.ramp_tag.value + self.ramp,
                                      self.setpoint_tag.value)
        else:
            self.ramp_tag.value = max(self.ramp_tag.value - self.ramp,
                                      self.setpoint_tag.value)


class Average():
    """Average a value."""

    def __init__(self, tag: Tag, count=60) -> None:
        """Average."""
        self.tag = tag
        self.count = count
        self.samples = []

    def step(self, sample: float) -> None:
        """Take a sample, update tag value if count samples taken."""
        self.samples.append(sample)
        if len(self.samples) == self.count:
            self.tag.value = sum(self.samples) / self.count
            self.samples = []
