"""Test Samplers."""
import pymscada.samplers as ps
from pymscada import Tag


def test_get_cpu_temp():
    """Check CPU calc."""
    if not ps.CPU_TEMP:
        return
    cpu_temp = ps.get_cpu_temp()
    assert cpu_temp > 0 and cpu_temp < 200


def test_get_cpu_load():
    """Check CPU calc."""
    cpu_load = ps.get_cpu_load()
    assert cpu_load >= 0 and cpu_load <= 100


def test_get_disk_use():
    """Check CPU calc."""
    disk_use = ps.get_disk_use()
    assert disk_use >= 0 and disk_use <= 100


def test_ramp():
    """Ramp."""
    settag = Tag('set001', float)
    ramptag = Tag('ramp001', float)
    ramp = ps.Ramp(ramptag, settag, 5)
    ramp.step()
    assert ramptag.value is None
    settag.value = 50
    ramp.step()
    assert ramptag.value == 50
    settag.value = 49.5
    ramp.step()
    assert ramptag.value == 49.5
    settag.value = 100
    ramp.step()
    assert ramptag.value == 54.5


def test_average():
    """Ramp."""
    avgtag = Tag('avg001', float)
    average = ps.Average(avgtag, count=5)
    for i in range(5):
        average.step(i)
    assert avgtag.value == 2
