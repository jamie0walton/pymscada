"""Test Observer class."""
import pytest
import time
import yaml
from pymscada.bus_client import BusClient
from pymscada.bus_client_tag import TagFloat, TagInt
from pymscada.observer import Observer, Valve, Math

BUS_ID = 999
CONFIG_YAML = """
math:
  SO_Sum_Gen:
  - {action: add, tagname: I_Aniwhenua_G1_MW}
  - {action: add, tagname: I_Aniwhenua_G2_MW}
  SO_Barrage_flow:
  - {action: add, tagname: SO_RadialGate_1_flow}
  - {action: add, tagname: SO_RadialGate_2_flow}
  - {action: add, tagname: SO_FlapGate_1_flow}
  - {action: add, tagname: SO_FlapGate_2_flow}
  - {action: add, tagname: SO_FlapGate_3_flow}
  SO_Lake_Aniwhenua_Inflow:
  - {action: add, tagname: SO_Galatea_delay_flow}
  - {action: add, tagname: SO_Lake_Aniwhenua_Rainflow}
model:
  System_Inflow:
    element_type: valve
    flow: 0.0
    flow_read_tag: I_Galatea_flow
    destination: Galatea_River_site
  RainFlow_1:
    element_type: valve
    flow: 1.1
    rate: 0.000166667
    destination: Galatea_River_site
  Galatea_River_site:
    element_type: summing
  Upper:
    element_type: river
    source: Galatea_River_site
    destination: Lake_Aniwhenua
    delay: 13800
    outflow_write_tag: SO_Galatea_delay_flow
  RainFlow_2:
    element_type: valve
    flow: 20.0
    rate: 0.0166667
    destination: Lake_Aniwhenua
  Lake_Aniwhenua:
    element_type: storage_rain_est
    # as tested on 4 days recorded data
    alpha: 1.001  # inflates predicted P each step
    Q:  # covariance of the process noise
    - [ 0.001,  0.002, 0.0001] # volume model good, some correlation with flows
    - [ 0.002,      1, 0.0005] # flow model OK, less correlation between flows
    - [0.0001, 0.0005,  0.001] # some rainflow drift is ok
    R:  # covariance of the observation noise
    - [500000, 0, 0]  # large as volume and sensitivity to sensor bounce
    - [     0, 1, 0]  # flow measurement is OK
    - [     0, 0, 1]
    LV: # mRL, m3
      - [145.00,  0]  # 0
      - [145.10,  90601]  # 100668
      - [145.20,  184249]  # 204721
      - [145.30,  280883]  # 312092
      - [145.40,  380471]  # 422746
      - [145.50,  482962]  # 536624
      - [145.60,  588314]  # 653682
      - [145.70,  696475]  # 773861
      - [145.80,  807413]  # 897126
      - [145.90,  921068]  # 1023409
      - [146.00,  1037401]  # 1152668
      - [146.10,  1156366]  # 1284851
      - [146.20,  1277924]  # 1419916
      - [146.30,  1402021]  # 1557801
      - [146.40,  1528612]  # 1698458
      - [146.50,  1657657]  # 1841841
      - [146.60,  1789111]  # 1987901
      - [146.70,  1922927]  # 2136585
      - [146.80,  2059052]  # 2287835
      - [146.90,  2197454]  # 2441615
      - [147.00,  2338079]  # 2597866
      - [148.00,  2523182]  # 2803536

# Scaled by 0.855 from reported as this gave a smaller
# calculated flow error while keeping Galatea at x1 at ~ 35 cumecs
# and Generator flow x1 at ~ 55 cumecs
#      - [145.00,       0]
#      - [148.00, 3278990] # extended the last range
    level_read_tag: I_Lake_Aniwhenua_level
    rainflow_write_tag: SO_Lake_Aniwhenua_Rainflow
  Aniwhenua_G1:
    element_type: generator
    MW: 0.0
    flow: 0.0
    source: Lake_Aniwhenua
    PQ:
      - [0.0,  0.0]
      - [0.1,  0.0]
      - [0.2,  8.0]
      - [1.0,  10.9]
      - [2.0,  13.4]
      - [3.0,  15.5]
      - [4.0,  17.3]
      - [6.0,  20.8]
      - [6.8,  22.2]
      - [8.0,  24.4]
      - [9.0,  26.5]
      - [10.0, 29.0]
      - [11.0, 32.0]
      - [12.0, 35.6]
      - [12.8, 38.9]
    MW_read_tag: I_Aniwhenua_G1_MW
    flow_write_tag: SO_Aniwhenua_G1_flow
  Aniwhenua_G2:
    element_type: generator
    MW: 0.0
    flow: 0.0
    source: Lake_Aniwhenua
    PQ: # power vs. flow
      - [0.0,  0.0]
      - [0.1,  0.0]
      - [0.2,  8.0]
      - [1.0,  10.9]
      - [2.0,  13.4]
      - [3.0,  15.5]
      - [4.0,  17.3]
      - [6.0,  20.8]
      - [6.8,  22.2]
      - [8.0,  24.4]
      - [9.0,  26.5]
      - [10.0, 29.0]
      - [11.0, 32.0]
      - [12.0, 35.6]
      - [12.8, 38.9]
    MW_read_tag: I_Aniwhenua_G2_MW
    flow_write_tag: SO_Aniwhenua_G2_flow
  RadialGate_1:
    element_type: radial_gate
    position: 0.0
    flow: 0.0
    level: 0.0
    source: Lake_Aniwhenua
    width: 9.65
    crest: 137.8
    PO: # position vs. opening
      - [0.0,  0.0]
      - [5.0,  0.32567545]
      - [10.0, 0.664181141]
      - [15.0, 1.014751678]
      - [20.0, 1.376594383]
      - [25.0, 1.748891092]
      - [30.0, 2.130800003]
      - [35.0, 2.521457581]
      - [40.0, 2.919980507]
      - [45.0, 3.325467679]
      - [50.0, 3.73700225]
      - [55.0, 4.153653695]
      - [60.0, 4.574479922]
      - [65.0, 4.998529399]
      - [70.0, 5.424843307]
      - [75.0, 5.852457703]
      - [80.0, 6.280405709]
      - [85.0, 6.707719687]
      - [90.0, 7.133433438]
      - [95.0, 7.556584377]
      - [100.0, 7.976215715]
    position_read_tag: I_RadialGate_1_pos
    level_read_tag: I_Lake_Aniwhenua_level
    flow_write_tag: SO_RadialGate_1_flow
  RadialGate_2:
    element_type: radial_gate
    position: 0.0
    flow: 0.0
    level: 0.0
    source: Lake_Aniwhenua
    width: 9.65
    crest: 137.8
    PO: # position vs. opening
      - [0.0,  0.0]
      - [5.0,  0.32567545]
      - [10.0, 0.664181141]
      - [15.0, 1.014751678]
      - [20.0, 1.376594383]
      - [25.0, 1.748891092]
      - [30.0, 2.130800003]
      - [35.0, 2.521457581]
      - [40.0, 2.919980507]
      - [45.0, 3.325467679]
      - [50.0, 3.73700225]
      - [55.0, 4.153653695]
      - [60.0, 4.574479922]
      - [65.0, 4.998529399]
      - [70.0, 5.424843307]
      - [75.0, 5.852457703]
      - [80.0, 6.280405709]
      - [85.0, 6.707719687]
      - [90.0, 7.133433438]
      - [95.0, 7.556584377]
      - [100.0, 7.976215715]
    position_read_tag: I_RadialGate_2_pos
    level_read_tag: I_Lake_Aniwhenua_level
    flow_write_tag: SO_RadialGate_2_flow
  FlapGate_1:
    element_type: flap_gate
    position: 0.0
    flow: 0.0
    level: 0.0
    source: Lake_Aniwhenua
    PC: # position vs. crest
      - [0.0, 146.88]
      - [6.0, 146.812]
      - [12.0, 146.725]
      - [18.0, 146.618]
      - [25.0, 146.471]
      - [33.0, 146.275]
      - [41.0, 146.053]
      - [50.0, 145.776]
      - [60.0, 145.441]
      - [71.0, 145.05]
      - [72.0, 145.026]
      - [87.0, 144.8]
      - [100.0, 144.8]
    HQ: # head vs. flow
      - [0.0, 0.0]
      - [0.1, 0.581268471]
      - [0.2, 1.643746629]
      - [0.3, 3.019151188]
      - [0.4, 4.64735712]
      - [0.6, 8.534322367]
      - [0.8, 13.13418675]
      - [1.1, 21.16392245]
      - [1.4, 30.36952208]
      - [1.8, 44.23908244]
      - [2.2, 59.72862862]
      - [2.6, 76.67599718]
      - [3.0, 94.95807472]
    position_read_tag: I_FlapGate_1_pos
    level_read_tag: I_Lake_Aniwhenua_level
    flow_write_tag: SO_FlapGate_1_flow
  FlapGate_2:
    element_type: flap_gate
    position: 0.0
    flow: 0.0
    level: 0.0
    source: Lake_Aniwhenua
    PC: # position vs. crest
      - [0.0, 146.88]
      - [6.0, 146.812]
      - [12.0, 146.725]
      - [18.0, 146.618]
      - [25.0, 146.471]
      - [33.0, 146.275]
      - [41.0, 146.053]
      - [50.0, 145.776]
      - [60.0, 145.441]
      - [71.0, 145.05]
      - [72.0, 145.026]
      - [87.0, 144.8]
      - [100.0, 144.8]
    HQ: # head vs. flow
      - [0.0, 0.0]
      - [0.1, 0.581268471]
      - [0.2, 1.643746629]
      - [0.3, 3.019151188]
      - [0.4, 4.64735712]
      - [0.6, 8.534322367]
      - [0.8, 13.13418675]
      - [1.1, 21.16392245]
      - [1.4, 30.36952208]
      - [1.8, 44.23908244]
      - [2.2, 59.72862862]
      - [2.6, 76.67599718]
      - [3.0, 94.95807472]
    position_read_tag: I_FlapGate_2_pos
    level_read_tag: I_Lake_Aniwhenua_level
    flow_write_tag: SO_FlapGate_2_flow
  FlapGate_3:
    element_type: flap_gate
    position: 0.0
    flow: 0.0
    level: 0.0
    source: Lake_Aniwhenua
    PC: # position vs. crest
      - [0.0, 146.88]
      - [6.0, 146.812]
      - [12.0, 146.725]
      - [18.0, 146.618]
      - [25.0, 146.471]
      - [33.0, 146.275]
      - [41.0, 146.053]
      - [50.0, 145.776]
      - [60.0, 145.441]
      - [71.0, 145.05]
      - [72.0, 145.026]
      - [87.0, 144.8]
      - [100.0, 144.8]
    HQ: # head vs. flow
      - [0.0, 0.0]
      - [0.1, 0.581268471]
      - [0.2, 1.643746629]
      - [0.3, 3.019151188]
      - [0.4, 4.64735712]
      - [0.6, 8.534322367]
      - [0.8, 13.13418675]
      - [1.1, 21.16392245]
      - [1.4, 30.36952208]
      - [1.8, 44.23908244]
      - [2.2, 59.72862862]
      - [2.6, 76.67599718]
      - [3.0, 94.95807472]
    position_read_tag: I_FlapGate_3_pos
    level_read_tag: I_Lake_Aniwhenua_level
    flow_write_tag: SO_FlapGate_3_flow
"""
CONFIG = yaml.safe_load(CONFIG_YAML)


@pytest.fixture(scope='module')
def o():
    """Create BusClient and set callback, but never start it."""
    _client = BusClient(None, None)
    observer = Observer(bus_ip=None, **CONFIG)
    for name, config in observer.model_config.items():
        observer.add_element(name, config)
    for name, config in observer.math_config.items():
        observer.math[name] = Math(p=observer, name=name, element_type='math',
                                   calc=config)
    yield observer


@pytest.fixture(scope='module')
def t():
    """Create all tags from CONFIG."""
    tags = {}
    for _element_name, element_config in CONFIG['model'].items():
        for key, value in element_config.items():
            if key.endswith('_read_tag') or key.endswith('_write_tag'):
                if value not in tags:
                    tags[value] = TagFloat(value)
    yield tags


def test_observer_create_with_valve_flow(o):
    """Instantiate Observer with valve-only config, confirm creation, stop."""
    assert 'System_Inflow' in o.model
    assert isinstance(o.model['System_Inflow'], Valve)
    assert o.model['System_Inflow'].name == 'System_Inflow'
    assert o.model['System_Inflow'].flow_read_tag is not None


def test_valve(o, t):
    """Test valve simulation."""
    valve_1 = o.model['System_Inflow']
    valve_2 = o.model['RainFlow_1']
    valve_3 = o.model['RainFlow_2']
    valve_1.initialise()
    assert valve_1.flow == 0.0
    t['I_Galatea_flow'].set_value(123.0, 600000000, BUS_ID)
    assert valve_1.flow == 123.0
    # ramp up
    valve_3.flow = 10.0
    valve_3.setFlow = 50.0
    valve_3.rate = 5.0
    valve_3.simulate_step()
    assert valve_3.flow == 15.0
    # ramp down
    valve_3.flow = 100.0
    valve_3.setFlow = 20.0
    valve_3.rate = 50.0
    valve_3.simulate_step()
    assert valve_3.flow == 50.0
    valve_3.simulate_step()
    assert valve_3.flow == 20.0


def test_summing(o, t):
    """Test summing, simulation and following are identical."""
    inflow_1 = o.model['System_Inflow']
    inflow_2 = o.model['RainFlow_1']
    summing = o.model['Galatea_River_site']
    outflow = o.model['Upper']
    inflow_1.link()
    inflow_2.link()
    with pytest.raises(ValueError, match="one river required"):
        summing.follow_step()
    outflow.link()
    t['I_Galatea_flow'].set_value(5.0, 0, BUS_ID)
    inflow_1.simulate_step()  # need to simulate valve, not follow
    inflow_2.flow = 3.0  # directly sets, no simulate_step reqd
    summing.follow_step()
    assert outflow.inflow == pytest.approx(5.0 + 3.0)


def test_river(o, t):
    """Test river delay line. Simulation and following are identical."""
    river = o.model['Upper']
    river.inflow = 12.3
    river.initialise()  # fills delayline with inflow
    assert len(river.delayline) == 13800  # delay in seconds
    river.inflow = 0.0
    river.simulate_step()
    assert t['SO_Galatea_delay_flow'].value == 12.3
    volume = t['SO_Galatea_delay_flow'].value
    for _ in range(29):
        river.simulate_step()
        volume += river.outflow
    assert volume == pytest.approx(12.3 * 30)  # 12.3 * 30 seconds


def test_storage_rain_est(o, t):
    storage = o.model['Lake_Aniwhenua']
    inflow = o.model['RainFlow_2']
    outflow = o.model['Aniwhenua_G1']
    inflow.link()
    outflow.link()
    inflow.flow = 40.0
    outflow.flow = 50.0
    storage.level = 146.70
    storage.initialise()
    assert storage.volume == 1922927
    for _ in range(60 * 10):
        storage.simulate_step()
        storage.volume += 5.0
        storage.recalc_level()
        storage.follow_step()
    assert storage.rainflow == pytest.approx(5.0, abs=1.0)
    storage.volume = 90601.0
    storage.recalc_level()
    assert storage.level == pytest.approx(145.10)


def test_generator(o, t):
    generator = o.model['Aniwhenua_G1']
    generator.initialise()
    assert generator.flow == 0.0
    generator.MW = 10.0
    generator.follow_step()
    assert generator.flow == pytest.approx(29.0)
    generator.MW = 0.0
    generator.setMW = 10.0
    generator.rate = 0.01
    generator.simulate_step()
    assert generator.MW == pytest.approx(0.01)
    generator.simulate_step()
    assert generator.MW == pytest.approx(0.02)


def test_radial_gate(o, t):
    gate = o.model['RadialGate_1']
    gate.initialise()
    assert gate.flow == 0.0
    gate.position = 5.0
    gate.level = 146.6
    gate.follow_step()
    assert gate.flow == pytest.approx(30, abs=1.0)
    gate.position = 0.0
    gate.setposition = 50.0
    gate.rate = 0.01
    gate.simulate_step()
    assert gate.position == pytest.approx(0.01)
    gate.simulate_step()
    assert gate.position == pytest.approx(0.02)


def test_flap_gate(o, t):
    gate = o.model['FlapGate_1']
    gate.initialise()
    assert gate.flow == 0.0
    gate.position = 50.0
    gate.level = 145.776 + 0.2
    gate.follow_step()
    assert gate.flow == pytest.approx(1.643746629)
    gate.position = 0.0
    gate.setposition = 50.0
    gate.rate = 0.01
    gate.simulate_step()
    assert gate.position == pytest.approx(0.01)
    gate.simulate_step()
    assert gate.position == pytest.approx(0.02)


def test_math(o, t):
    """Test math element calculations."""
    math_sum_gen = o.math['SO_Sum_Gen']
    assert math_sum_gen.output_tag.name == 'SO_Sum_Gen'
    assert len(math_sum_gen.input_tags) == 2
    t['I_Aniwhenua_G1_MW'].set_value(5.0, 0, BUS_ID)
    assert math_sum_gen.output_tag.value == pytest.approx(5.0)
    t['I_Aniwhenua_G2_MW'].set_value(7.0, 0, BUS_ID)
    assert math_sum_gen.output_tag.value == pytest.approx(12.0)
    math_sum_gen.follow_step()
    assert math_sum_gen.output_tag.value == pytest.approx(12.0)
