"""Test Math class."""
import pytest
from pymscada.bus_client import BusClient
from pymscada.bus_client_tag import TagFloat
from pymscada.math import Math, MathElement

BUS_ID = 999
CONFIG = {
    'SO_Sum_Gen': [
        {'action': 'add', 'tagname': 'I_Aniwhenua_G1_MW'},
        {'action': 'add', 'tagname': 'I_Aniwhenua_G2_MW'}
    ],
    'SO_Barrage_flow': [
        {'action': 'add', 'tagname': 'SO_RadialGate_1_flow'},
        {'action': 'add', 'tagname': 'SO_RadialGate_2_flow'},
        {'action': 'add', 'tagname': 'SO_FlapGate_1_flow'},
        {'action': 'add', 'tagname': 'SO_FlapGate_2_flow'},
        {'action': 'add', 'tagname': 'SO_FlapGate_3_flow'}
    ]
}


@pytest.fixture(scope='module')
def m():
    """Create Math module but never start it."""
    _client = BusClient(None, None)
    math = Math(bus_ip=None, config=CONFIG)
    for name, calc_config in math.config.items():
        element = MathElement(name, calc_config)
        math.elements[name] = element
        for tag in element.input_tags:
            if tag.name not in math.input_tags:
                math.input_tags[tag.name] = tag
    yield math


@pytest.fixture(scope='module')
def t():
    """Create all tags from CONFIG."""
    tags = {}
    for _element_name, calc_config in CONFIG.items():
        for action in calc_config:
            if 'tagname' in action:
                tagname = action['tagname']
                if tagname not in tags:
                    tags[tagname] = TagFloat(tagname)
    yield tags


def test_math_element_create(m):
    """Test MathElement creation."""
    assert 'SO_Sum_Gen' in m.elements
    element = m.elements['SO_Sum_Gen']
    assert element.output_tag.name == 'SO_Sum_Gen'
    assert len(element.input_tags) == 2


def test_math_element_calc(m, t):
    """Test math element calculations."""
    element = m.elements['SO_Sum_Gen']
    t['I_Aniwhenua_G1_MW'].set_value(5.0, 0, BUS_ID)
    assert element.output_tag.value == pytest.approx(5.0)
    t['I_Aniwhenua_G2_MW'].set_value(7.0, 0, BUS_ID)
    assert element.output_tag.value == pytest.approx(12.0)
    element.follow_step()
    assert element.output_tag.value == pytest.approx(12.0)


def test_math_element_multiple_inputs(m, t):
    """Test math element with multiple inputs."""
    element = m.elements['SO_Barrage_flow']
    assert len(element.input_tags) == 5
    t['SO_RadialGate_1_flow'].set_value(10.0, 0, BUS_ID)
    t['SO_RadialGate_2_flow'].set_value(20.0, 0, BUS_ID)
    t['SO_FlapGate_1_flow'].set_value(5.0, 0, BUS_ID)
    t['SO_FlapGate_2_flow'].set_value(15.0, 0, BUS_ID)
    t['SO_FlapGate_3_flow'].set_value(25.0, 0, BUS_ID)
    element.follow_step()
    assert element.output_tag.value == pytest.approx(75.0)
