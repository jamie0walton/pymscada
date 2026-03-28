import subprocess
import sys
import pytest
import time
from yaml import safe_load
from pymscada.bus_client_tag import TagDict, TagFloat, TagInt
from pymscada.mp_control import MPControl

BUS_ID = 999
TAGS = {
    '_mpc_control': [int, 0],
    '_mpc_solve_time': [int, 0],
    '_mpc_last_solve': [int, 0],
    'dispatch_setMW': [float, 12.3],
    '_mpc_result': [dict, {}],
    'I_Galatea_flow': [float, 60.0],
    'SO_Lake_Aniwhenua_Rainflow': [float, 2.3],
    'I_Lake_Aniwhenua_level': [float, 146.7],
    'I_Aniwhenua_G1_MW': [float, 10.333],
    'I_Aniwhenua_G2_MW': [float, 10.333],
    'SO_Barrage_flow': [float, 2.3],
}


@pytest.fixture(scope='module')
def mpcontrol():
    """Create Math module but never start it."""
    cfg = safe_load(open('src/pymscada/demo/mp_control.yaml'))
    cfg['bus_ip'] = None
    yield MPControl(**cfg)


@pytest.fixture(scope='module')
def tags():
    """Create all tags from CONFIG."""
    now = int(time.time() * 1e6)
    tags: dict[str, TagFloat | TagInt | TagDict] = {}
    for tagname, (tagtype, value) in TAGS.items():
        if tagtype == float:
            tags[tagname] = TagFloat(tagname)
        elif tagtype == int:
            tags[tagname] = TagInt(tagname)
        elif tagtype == dict:
            tags[tagname] = TagDict(tagname)
        tags[tagname].set_value(value, now, BUS_ID)
    yield tags


def test_mp_control_run():
    r = subprocess.run(
        [sys.executable, '-m', 'pymscada', 'mp_control', '-h'],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0
    assert 'usage' in (r.stdout + r.stderr).lower()


@pytest.mark.asyncio
async def test_mpc_flat_profile(mpcontrol, tags):
    """Create the MPCRunner and test callbacks."""
    now = int(time.time() * 1e6)
    await mpcontrol.start()
    mpcontrol.runner.make_model(now)
    m = mpcontrol.runner.model['model']
    assert m['Upper']['time_series'].get(now) == 60.0
    assert m['Lake_Aniwhenua']['time_series'].get(now) == 146.7
    mpcontrol.runner.hydraulic_model.solve_lp()
    results = mpcontrol.runner.hydraulic_model.lp.resultsdict
    for t in results['Lake_Aniwhenua']['Level']:
        assert results['Lake_Aniwhenua']['Level'][t] == pytest.approx(146.7)
