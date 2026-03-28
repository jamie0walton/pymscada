"""Test hydraulic model."""
import pytest
from itertools import count
from pymscada.milp.model_hyd import HydraulicModel, TimeSeries, State, \
                                    interp, Constraint


def test_ts_basic():
    ts1 = TimeSeries()
    ts2 = TimeSeries()
    ts1.value = 123
    ts2.value = -1
    ts2.set({200: 1000, 50: 1, 100: 10})
    assert ts1.get(1) == 123
    assert ts2.get(0) == -1
    assert ts2.get(75) == 1
    assert ts2.get(175) == 10
    assert ts2.get(500) == 1000


# Power MW, Flow cumecs
PQ = [
    [0.0, 0.0],
    [0.01, 8.0],
    [6.8, 22.2],
    [10.0, 30.2],
    [12.8, 47.7]
]
# Level mm, volume m3
LV = [
    [145.00, 0],
    [145.10, 117740],
    [145.20, 239440],
    [145.30, 365020],
    [145.40, 494440],
    [145.50, 627630],
    [145.60, 764540],
    [145.70, 905100],
    [145.80, 1049270],
    [145.90, 1196970],
    [146.00, 1348150],
    [146.10, 1502750],
    [146.20, 1660720],
    [146.30, 1821990],
    [146.40, 1986500],
    [146.50, 2154200],
    [146.60, 2325030],
    [146.70, 2498930],
    [146.80, 2675830],
    [146.90, 2855690],
    [147.00, 3038440],
    [148.00, 3278990]
]


def get_samples(m, element, parameter, times):
    """Planning to use this a lot."""
    series = m.lp.resultsdict[element][parameter]
    result = []
    for t in times:
        if t in series:
            result.append(series[t])
        else:
            result.append(None)
    return result


def test_interp():
    """Interpolates outside of the points deliberately."""
    xs = [x[0] for x in LV]
    ys = [x[1] for x in LV]
    assert interp(145.05, xs, ys) == pytest.approx(58870)
    assert interp(144.90, xs, ys) == pytest.approx(-117740)
    assert interp(147.25, xs, ys) == pytest.approx(3098577.5)
    assert interp(148.25, xs, ys) == pytest.approx(3339127.5)


def test_range_conform():
    """Should limit to range."""
    c1 = Constraint(ranges=[[1.0, 2.0]])
    assert c1._range_conform(0.0) == 1.0
    c2 = Constraint(ranges=[[1.0], [1.0, 2.0]])
    assert c2._range_conform(0.0) == 0.0
    c3 = Constraint(ranges=[[1.0, 3.0], [6.8, 12.6]])
    assert c3._range_conform(0.0) == 1.0
    assert c3._range_conform(110.0) == 12.6
    c4 = Constraint(ranges=[[0.0], [1.0, 3.0], [6.8, 12.6]])
    assert c4._range_conform(5.0) == 6.8


def test_model_times():
    """Make sure that the time sequences are as expected."""
    inflow = TimeSeries({
        12342665: 9.0,
        12343665: 8.0,
        12344665: 7.0,
        12345665: 6.0
    })
    model = {
        'name': 'test',
        'actual_time': 123456651,
        'time_step': 600,
        'duration': 1200,
        'tempdir': 'tmp',
        'model': {
            'Valve': {
                'type': 'valve',
                'time_series': inflow,
                'state': State.OFF
            },
            'River': {
                'type': 'river',
                'time_series': inflow,
                'srcnode': 'Valve',
                'delay': 600
            }
        }
    }
    m = HydraulicModel(model)
    m.solve_lp()
    # No time clash
    assert m.start_time == 123456600
    assert m.actual_time == 123456651
    assert m.set_time == 123456652
    assert m.end_time == 123457800
    assert m.times == [123456600,  # start_time
                       123456651,  # actual_time
                       123456652,  # set_time
                       123457200,  # interval step - normally more
                       123457800]  # end_time
    m.set_actual_time(123456600)
    m.solve_lp()
    # TODO check that the 1 second move is necessary
    # remove if not.
    # slip evaluation time back 1 second
    assert m.start_time == 123456600
    assert m.actual_time == 123456601
    assert m.set_time == 123456602
    assert m.end_time == 123457800
    assert m.times == [123456600,  # start_time
                       123456601,  # actual_time
                       123456602,  # set_time
                       123457200,  # interval step - normally more
                       123457800]  # end_time
    m.set_actual_time(123457199)
    m.solve_lp()
    # push evaluation time forward 1 second
    assert m.start_time == 123456600
    assert m.actual_time == 123457198
    assert m.set_time == 123457199
    assert m.end_time == 123457800
    assert m.times == [123456600,  # start_time
                       123457198,  # actual_time
                       123457199,  # set_time
                       123457200,  # interval step - normally more
                       123457800]  # end_time
    m.remove_result()


def test_tank_fixed():
    """Simple fill / empty tank with fixed flows to check the math."""
    inflow = TimeSeries(9.0)
    outflow = TimeSeries(1.0)
    tank = TimeSeries(0.5)
    model = {
        'name': 'test',
        'actual_time': 1522494300,
        'time_step': 600,
        'duration': 1200,
        'tempdir': 'tmp',
        'model': {
            'Inflow': {
                'type': 'valve',
                'time_series': inflow,
                'dstnode': 'Tank',
                'state': State.FIXED
            },
            'Tank': {
                'type': 'storage',
                'time_series': tank,
                'LV': [
                    [0.00, 0],
                    [1.00, 1000000]
                ],
                # This cost approach I consider computationally
                # expensive. Use SPARINGLY.
                'costs': [
                    [0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
                    [
                        [10000, 10000],  # expensive low cost
                        [50, 10],  # soft low cost
                        [1, 0],  # slightly favour filling
                        [0, 50],  # soft high cost
                        [5000, 5000]  # expensive high cost
                    ]
                ]
            },
            'Outflow': {
                'type': 'valve',
                'time_series': outflow,
                'srcnode': 'Tank',
                'state': State.FIXED
            }
        }
    }
    m = HydraulicModel(model)
    m.solve_lp()
    assert inflow.times() == [0, 1522494000, 1522494300, 1522494301,
                              1522494600, 1522495200]
    assert inflow.values() == [9, 9, 9, 9, 9, 9]
    assert tank.values() == [0.5, 0.5, 0.500008, 0.5024, 0.5072]
    assert outflow.values() == [1, 1, 1, 1, 1, 1]
    m.remove_result()


def test_tank_fixed_river():
    """Simple fill / empty tank with fixed flows and river delay."""
    inflow = TimeSeries({
        1522492200: 9.0,
        1522492800: 8.0,
        1522493400: 7.0,
        1522494300: 6.0
    })
    outflow = TimeSeries(1.0)
    tank = TimeSeries(0.5)
    model = {
        'name': 'test',
        'actual_time': 1522494300,
        'time_step': 600,
        'duration': 2400,
        'tempdir': 'tmp',
        'model': {
            'Inflow': {
                'type': 'valve',
                'time_series': inflow,
                'dstnode': 'Upstream',
                'state': State.FIXED
            },
            'Upstream': {
                'type': 'summing'
            },
            'River': {
                'type': 'river',
                'time_series': inflow,
                'srcnode': 'Upstream',
                'dstnode': 'Tank',
                'delay': 1200
            },
            'Tank': {
                'type': 'storage',
                'time_series': tank,
                'LV': [
                    [0.00, 0],
                    [1.00, 1000000]
                ],
                'min': 0.4,
                'max': 0.6,
                'setpoint': 0.5,
                'highcost': 1,
                'lowcost': 1,
                'costs': [
                    [0, .49, 0.51, 1],
                    [[100, 100], [0, 0], [100, 100]]
                ]
            },
            'Outflow': {
                'type': 'valve',
                'time_series': outflow,
                'srcnode': 'Tank',
                'state': State.FIXED
            }
        }
    }
    m = HydraulicModel(model)
    m.solve_lp()
# phase  time        inflow delayed outflow volume
#        1522492200  9
#        1522492800  8
#        1522493400  7      9
# start  1522494000  7      8
# actual 1522494300  6      8       1       500000
# set    1522494301  6      8       1       500007
#        1522494600  6      7       1       502100
#        1522495200  6      7       1       505700
#        1522495800  6      6       1       509300
# end    1522496400  6      6       1       512300
    assert inflow.times() == [1522492200, 1522492800, 1522493400, 1522494000,
                              1522494300, 1522494301, 1522494600, 1522495200,
                              1522495800, 1522496400]
    assert inflow.values() == [9, 8, 7, 7, 6, 6, 6, 6, 6, 6]
    assert tank.values() == [0.5, 0.5, 0.500007, 0.5021, 0.5057, 0.5093,
                             0.5123]
    assert outflow.values() == [1, 1, 1, 1, 1, 1, 1, 1]
    assert m.lp.solutioncost == 29507
    m.remove_result()


def test_tank_variable_empty():
    """Tank outflow (slack) should have an optimum solution."""
    inflow = TimeSeries({1522494000: 500.0})
    outflow = TimeSeries({1522494000: 1.0})
    tank = TimeSeries(0.5)
    model = {
        'name': 'test',
        'actual_time': 1522494300,
        'time_step': 600,
        'duration': 3600,
        'tempdir': 'tmp',
        'model': {
            'Inflow': {
                'type': 'valve',
                'time_series': inflow,
                'dstnode': 'Tank',
                'state': State.FIXED
            },
            'Tank': {
                'type': 'storage',
                'time_series': tank,
                'min': 0.4,
                'max': 0.6,
                'LV': [
                    [0.00, 0],
                    [1.00, 1000000]
                ]
            },
            'Outflow': {
                'type': 'valve',
                'time_series': outflow,
                'state': State.FREE,
                'srcnode': 'Tank',
                'ranges': [
                    [0.0, 1000.0]
                ],
                'setpoint': 0,
                'highcost': 100  # will delay outflow
            },
            'OutflowChange': {
                'type': 'change_cost',
                'cost': 1.0,
                'element': 'Outflow'
            }
        }
    }
    m = HydraulicModel(model)
    m.solve_lp()
    assert inflow.times() == [1522494000, 1522494300, 1522494301, 1522494600,
                              1522495200, 1522495800, 1522496400, 1522497000,
                              1522497600]
    assert tank.values() == pytest.approx([0.5, 0.5, 0.500499, 0.6, 0.6, 0.6,
                                           0.6, 0.6, 0.6])
    assert outflow.values() == pytest.approx([1, 1, 167.22074, 500, 500, 500,
                                              500, 500, 0])
    assert m.lp.solutioncost == pytest.approx(267721.07358)
    m.remove_result()


def test_tank_variable_empty_profile_limits():
    """Tank outflow (slack) should solve within flow limits."""
    # Missed adding cost, gave a slightly different answer.
    inflow = TimeSeries({1522494000: 100.0})
    outflow = TimeSeries({1522494000: 1.0})
    tank = TimeSeries(0.5)
    model = {
        'name': 'test',
        'actual_time': 1522494300,
        'time_step': 600,
        'duration': 4 * 3600,
        'tempdir': 'tmp',
        'model': {
            'Inflow': {
                'type': 'valve',
                'time_series': inflow,
                'dstnode': 'Tank',
                'state': State.FIXED,
            },
            'Tank': {
                'type': 'storage',
                'time_series': tank,
                'costs': [
                    [0, 0.4, 0.6, 1],
                    [[0.4, 0.1], [0, 0], [0.1, 0.4]]
                ],
                'LV': [
                    [0.00, 0],
                    [1.00, 1000000]
                ]
            },
            'Outflow': {
                'type': 'valve',
                'time_series': outflow,
                'state': State.FREE,
                'srcnode': 'Tank',
                'ranges': [
                    [0.0, 1000.0]
                ]
            },
            'OutflowChange': {
                'type': 'change_cost',
                'cost': 10.0,  # Old ==1.0 This ==10.0 for same result
                'element': 'Outflow'
            },
            'MinFlow': {
                'type': 'limit_profile',
                'cost': 10,
                'min': True,
                'measurement': 'flow',
                'elements': [
                    'Outflow',
                ],
                'timeofday': [
                    [0.0 * 3600, 1.0],
                    [0.5 * 3600, 190.0],
                    [1.0 * 3600, 1.0],
                    [1.5 * 3600, 190.0],
                    [2.0 * 3600, 1.0],
                    [2.5 * 3600, 190.0],
                    [3.0 * 3600, 1.0],
                    [3.5 * 3600, 190.0]
                ]
            },
            'MaxFlow': {
                'type': 'limit_profile',
                'cost': 10,
                'max': True,
                'measurement': 'flow',
                'elements': [
                    'Outflow',
                ],
                'timeofday': [
                    [0.0 * 3600, 25.0],
                    [0.5 * 3600, 250.0],
                    [1.0 * 3600, 25.0],
                    [1.5 * 3600, 250.0],
                    [2.0 * 3600, 25.0],
                    [2.5 * 3600, 250.0],
                    [3.0 * 3600, 25.0],
                    [3.5 * 3600, 250.0]
                ]
            }
        }
    }
    m = HydraulicModel(model)
    m.solve_lp()
    results = m.lp.resultsdict
    times = list(results['Tank']['Level'].keys())[:8]
    levels = [results['Tank']['Level'][t] for t in times]
    outflows = [results['Outflow']['Flow'][t] for t in times]
    assert levels == pytest.approx([0.5, 0.500099, 0.52368, 0.571, 0.616,
                                   0.562, 0.508, 0.454])
    assert outflows == pytest.approx([1, 21.13348, 21.13348, 25, 190, 190,
                                     190, 25])
    assert m.lp.solutioncost == pytest.approx(11790.23225)
    m.remove_result()


def test_genprofile():
    """MW output to follow a profile."""
    power = TimeSeries({1522494000: 5.2, 1522494300: 5.0})
    model = {
        'name': 'test',
        'actual_time': 1522494300,
        'time_step': 600,
        'duration': 1200,
        'tempdir': 'tmp',
        'model': {
            'G1': {
                'type': 'generator',
                'time_series': power,
                'state': State.FREE,
                'ranges': [
                    [6.8, 12.8]
                ],
                'PQ': PQ
            },
            'MWset': {
                'type': 'cost',
                'cost': 10,
                'measurement': 'power',
                'elements': [
                    'G1',
                ],
                'timeofday': [
                    [0, 3.0],
                    [600, 12.0],
                    [1200, 6.0]
                ]
            }
        }
    }
    m = HydraulicModel(model)
    m.solve_lp()
    results = m.lp.resultsdict
    times = list(results['G1']['Power'].keys())[:5]
    g1_power = [results['G1']['Power'][t] for t in times]
    g1_flow = [results['G1']['Flow'][t] for t in times]
    assert g1_power == pytest.approx([6.8, 6.8, 6.8, 12.0, 6.8])
    assert g1_flow == pytest.approx([22.2, 22.2, 22.2, 42.7, 22.2])
    assert m.lp.solutioncost == pytest.approx(46)
    m.remove_result()


def test_gentimeprofile():
    """MW output to follow a profile."""
    power = TimeSeries({1522494000: 5.2, 1522494300: 5.0})
    model = {
        'name': 'test',
        'actual_time': 1522494300,
        'time_step': 600,
        'duration': 2400,
        'tempdir': 'tmp',
        'model': {
            'G1': {
                'type': 'generator',
                'time_series': power,
                'state': State.FREE,
                'ranges': [
                    [6.8, 12.8]
                ],
                'PQ': PQ
            },
            'MWset': {
                'type': 'time_profile',
                'elements': [
                    'G1',
                ],
                'timeofday': [
                    [0, 0.0],
                    [1200, 20.0],
                    [2400, 0.0]
                ],
                'min': 0,
                'max': 12.8,
                'lowcost': 1,
                'highcost': 1
            }
        }
    }
    m = HydraulicModel(model)
    m.solve_lp()
    results = m.lp.resultsdict
    times = list(results['G1']['Power'].keys())[:7]
    g1_power = [results['G1']['Power'][t] for t in times]
    g1_flow = [results['G1']['Flow'][t] for t in times]
    assert g1_power == pytest.approx([6.8, 6.8, 6.8, 10.0, 12.8, 10.0, 6.8])
    assert g1_flow == pytest.approx([22.2, 22.2, 22.2, 30.2, 47.7, 30.2, 22.2])
    assert m.lp.solutioncost == pytest.approx(15.7833333)
    m.remove_result()


def test_gentimestep():
    """MW output to follow a profile."""
    power = TimeSeries({1522494000: 5.2, 1522494300: 5.0})
    model = {
        'name': 'test',
        'actual_time': 1522494300,
        'time_step': 600,
        'duration': 2400,
        'tempdir': 'tmp',
        'model': {
            'G1': {
                'type': 'generator',
                'time_series': power,
                'state': State.FREE,
                'ranges': [
                    [6.8, 12.8]
                ],
                'PQ': PQ
            },
            'MWset': {
                'type': 'time_profile',
                'elements': [
                    'G1',
                ],
                'step': True,
                'timeofday': [
                    [0, 7],
                    [1200, 11],
                    [2400, 10]
                ],
                'min': 0,
                'max': 12.8,
                'lowcost': 1,
                'highcost': 1
            }
        }
    }
    m = HydraulicModel(model)
    m.solve_lp()
    results = m.lp.resultsdict
    times = list(results['G1']['Power'].keys())[:7]
    g1_power = [results['G1']['Power'][t] for t in times]
    g1_flow = [results['G1']['Flow'][t] for t in times]
    assert g1_power == pytest.approx([6.8, 6.8, 7, 7, 11, 11, 10])
    assert g1_flow == pytest.approx([22.2, 22.2, 22.7, 22.7, 36.45, 36.45,
                                     30.2])
    assert m.lp.solutioncost == pytest.approx(0)
    m.remove_result()


def test_twogensemi():
    """MW output semi-continuous."""
    power1 = TimeSeries({1522494000: 5.2, 1522494300: 5.0})
    power2 = TimeSeries({1522494000: 5.2, 1522494300: 5.1})
    model = {
        'name': 'test',
        'actual_time': 1522494300,
        'time_step': 600,
        'duration': 1200,
        'tempdir': 'tmp',
        'model': {
            'G1': {
                'type': 'generator',
                'time_series': power1,
                'state': State.FREE,
                'ranges': [
                    [0.0],
                    [6.8, 12.8]
                ],
                'PQ': PQ
            },
            'G2': {
                'type': 'generator',
                'time_series': power2,
                'state': State.FREE,
                'ranges': [
                    [0.0],
                    [6.8, 12.8]
                ],
                'PQ': PQ
            },
            'MWset': {
                'type': 'cost',
                'cost': 10,
                'measurement': 'power',
                'elements': [
                    'G1',
                    'G2',
                ],
                'timeofday': [
                    [0, 3.0],
                    [600, 14.0],
                    [1200, 22.0]
                ]
            }
        }
    }
    m = HydraulicModel(model)
    m.solve_lp()
    results = m.lp.resultsdict
    times = list(results['G1']['Power'].keys())[:5]
    g1_power = [results['G1']['Power'][t] for t in times]
    g1_flow = [results['G1']['Flow'][t] for t in times]
    g2_power = [results['G2']['Power'][t] for t in times]
    g2_flow = [results['G2']['Flow'][t] for t in times]
    station = [sum(i) for i in zip(g1_power, g2_power)]
    station_flow = [sum(i) for i in zip(g1_flow, g2_flow)]
    assert station == pytest.approx([13.6, 13.6, 0.0, 14.0, 22.0])
    assert station_flow == pytest.approx([44.4, 44.4, 0.0, 45.4, 72.9])
    assert m.lp.solutioncost == pytest.approx(30.0)
    m.remove_result()


def test_twogensemi2():
    """MW output semi-continuous, 2 generators."""
    power1 = TimeSeries({1522494000: 5.2, 1522494300: 5.0})
    power2 = TimeSeries({1522494000: 5.2, 1522494300: 5.1})
    model = {
        'name': 'test',
        'actual_time': 1522494300,
        'time_step': 600,
        'duration': 600,
        'tempdir': 'tmp',
        'model': {
            'G1': {
                'type': 'generator',
                'time_series': power1,
                'state': State.FREE,
                'ranges': [
                    [0.0],  # always assumed as zero
                    [1.0, 3.0],
                    [6.8, 12.8]
                ],
                'PQ': PQ
            },
            'G2': {
                'type': 'generator',
                'time_series': power2,
                'state': State.FREE,
                'ranges': [
                    [0.0],  # always assumed as zero
                    [1.0, 3.0],
                    [6.8, 12.8]
                ],
                'PQ': PQ
            },
            'MWset': {
                'type': 'cost',
                'cost': 10,
                'measurement': 'power',
                'elements': [
                    'G1',
                    'G2',
                ],
                'timeofday': [
                    [0, 3.0],
                    [600, 26.0],
                ]
            }
        }
    }
    m = HydraulicModel(model)
    m.solve_lp()
    results = m.lp.resultsdict
    times = results['G1']['Power'].keys()
    g1_power = [results['G1']['Power'][t] for t in times]
    g2_power = [results['G2']['Power'][t] for t in times]
    station = [sum(i) for i in zip(g1_power, g2_power)]
    assert station == pytest.approx([13.6, 13.6, 3.0, 25.6])
    assert m.lp.solutioncost == pytest.approx(4)
    m.remove_result()


def test_gensemi_changeofstate():
    """
    MW output semi-continuous with start and range chanage limits.

    This is a fairly complex sequence and the right answer is not
    obvious. It was wrong before, now improved but still not fully
    checked as the math to check manually is getting long.
    """
    power1 = TimeSeries()
    for i, v in enumerate([0.01, 0.02, 0.03, 0.04, 0.05,
                           0.06, 0.07, 0.08, 11.0]):
        power1.set({1522489200 + i * 600: v})
    power1.set({1522494300: 11.0})
    model = {
        'name': 'test',
        'actual_time': 1522494300,
        'time_step': 600,
        'duration': 28 * 600,
        'tempdir': 'tmp',
        'model': {
            'G1': {
                'type': 'generator',
                'time_series': power1,
                'state': State.FREE,
                'startlimit': [1, 2400, 1000.0],  # 1 change in 2400 seconds
                'ranges': [
                    [0.0],  # always assumed as zero
                    [6.8, 12.8]
                ],
                'PQ': PQ
            },
            'MWset': {
                'type': 'cost',
                'cost': 10.0,
                'measurement': 'power',
                'elements': [
                    'G1'
                ],
                'timeofday': [
                    [0, 1.0],
                    [600, 2.0],
                    [1200, 3.0],
                    [1800, 2.0],
                    [2400, 1.0],
                    [3000, 2.0],
                    [3600, 3.0],
                    [4200, 2.0],
                    [4800, 1.0],
                    [5400, 11.0],
                    [6000, 1.0],
                    [6600, 11.0],
                    [7200, 1.0],
                    [7800, 11.0],
                    [8400, 1.0],
                    [9000, 0.0],
                    [9600, 0.0],
                    [10200, 0.0],
                    [10800, 0.0],
                    [11400, 0.0],
                    [12000, 12.0],
                    [12600, 12.0],
                    [13200, 0.0],
                    [13800, 0.0],
                    [14400, 0.0],
                    [15000, 0.0],
                    [15600, 0.0],
                    [16200, 0.0],
                    [16800, 0.0],
                ]
            }
        }
    }
    m = HydraulicModel(model)
    m.solve_lp()
    results = m.lp.resultsdict
    times = results['G1']['Power'].keys()
    g1_power = [results['G1']['Power'][t] for t in times]
    assert g1_power == pytest.approx([11, 11, 6.8, 6.8, 6.8, 6.8, 0, 0, 0, 0,
                                     0, 11, 6.8, 11, 6.8, 11, 0, 0, 0, 0, 0,
                                     0, 12, 12, 6.8, 6.8, 0, 0, 0, 0, 0, 0, 0,
                                     0])
    assert m.lp.solutioncost == pytest.approx(544)
    m.remove_result()


def test_valveriverlake():
    """
    Check volume and flows.

    History is clearly calculated in a different way, twice now :(.
    """
    upper = TimeSeries([
        1522491600: 4.0,
        1522492200: 5.0,
        1522492800: 6.0,
        1522493400: 7.0
    ])
    sysinflow = TimeSeries({1522494000: 14.0})
    lake = TimeSeries(146.33)
    model = {
        'name': 'test',
        'actual_time': 1522494189,
        'time_step': 600,
        'duration': 6000,
        'tempdir': 'tmp',
        'model': {
            'System_Inflow': {
                'type': 'valve',
                'time_series': sysinflow,
                'dstnode': 'Galatea_Site',
                'state': State.FIXED
            },
            'Galatea_Site': {
                'type': 'summing'
            },
            'Upper': {
                'type': 'river',
                'time_series': upper,
                'delay': 1800,
                'srcnode': 'Galatea_Site',
                'dstnode': 'Lake_Aniwhenua'
            },
            'Lake_Aniwhenua': {
                'type': 'storage',
                'time_series': lake,
                'LV': LV,
                'setpoint': 146.7,
                'lowcost': 0.000001,
                'highcost': 0.000001
            }
        }
    }
    m = HydraulicModel(model)
    m.solve_lp()
    results = m.lp.resultsdict
    times = sorted(results['Upper']['Flow_in'].keys())
    upperin = get_samples(m, 'Upper', 'Flow_in', times)
    upperout = get_samples(m, 'Upper', 'Flow_out', times)
    lakewl = get_samples(m, 'Lake_Aniwhenua', 'Level', times)
    assert upperin == [14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14]
    assert upperout == [None, 5, 5, 6, 7, 7, 14, 14, 14, 14, 14, 14, 14]
    assert lakewl == pytest.approx([None, 146.33, 146.33, 146.33125, 146.33343,
                                   146.33599, 146.33854, 146.34365, 146.34876,
                                   146.35386, 146.35897, 146.36407, 146.36918])
    assert m.lp.solutioncost == pytest.approx(6.611102)
    m.remove_result()


def test_lake_bidoffer():
    """
    Add bid profile lake and generation together.

    Time adjustment as per test_valveriverlake and overall cost was
    exactly right. Consistent shift in time at least.
    """
    upper = TimeSeries({1522491600: 60.0, 1522492200: 60.0,
                        1522492800: 60.0, 1522493400: 60.0})
    sysinflow = TimeSeries({1522494000: 60.0})
    power1 = TimeSeries({1522492200: 6.2, 1522494000: 6.0})
    power2 = TimeSeries({1522492200: 0.2, 1522494000: 0.0})
    lake = TimeSeries(146.6)
    model = {
        'name': 'test',
        'actual_time': 1522494300,
        'time_step': 600,
        'duration': 14400,
        'tempdir': 'tmp',
        'model': {
            'System_Inflow': {
                'type': 'valve',
                'time_series': sysinflow,
                'dstnode': 'Galatea_Site',
                'state': State.FIXED
            },
            'Galatea_Site': {
                'type': 'summing'
            },
            'Upper': {
                'type': 'river',
                'time_series': upper,
                'delay': 1800,
                'srcnode': 'Galatea_Site',
                'dstnode': 'Lake_Aniwhenua'
            },
            'Lake_Aniwhenua': {
                'type': 'storage',
                'time_series': lake,
                'LV': LV,
                'costs': [
                    [146.5, 146.6, 146.8, 146.9],
                    [[100000000, 1000000], [0, 0], [1000000, 100000000]]
                ]
            },
            'G1': {
                'type': 'generator',
                'time_series': power1,
                'state': State.FREE,
                'srcnode': 'Lake_Aniwhenua',
                'ranges': [
                    [6.8, 12.8]
                ],
                'PQ': PQ
            },
            'G2': {
                'type': 'generator',
                'time_series': power2,
                'state': State.FREE,
                'srcnode': 'Lake_Aniwhenua',
                'startlimit': [1, 1200, 1000.0],
                'ranges': [
                    [0.0],
                    [6.8, 12.8]
                ],
                'PQ': PQ
            },
            'G1Change': {
                'type': 'change_cost',
                'cost': 0.0000001,
                'element': 'G1'
            },
            'G2Change': {
                'type': 'change_cost',
                'cost': 0.0000001,
                'element': 'G2'
            },
            'Delta': {
                'type': 'delta_cost',
                'cost': 0.0000001,
                'elements': ['G1', 'G2']
            },
            'LakeProfile': {
                'type': 'profile',
                'cost': 0.0001,
                'lowcost': 0.00001,
                'element': 'Lake_Aniwhenua',
                'timeofday': [
                    [0 * 3600, 146.6],
                    [2 * 3600, 146.8],
                    [4 * 3600, 146.6],
                    [6 * 3600, 146.8],
                    [8 * 3600, 146.6],
                    [10 * 3600, 146.8],
                    [12 * 3600, 146.6],
                    [14 * 3600, 146.8],
                    [16 * 3600, 146.6],
                ],
                'LV': LV
            },
            'Bid': {
                'type': 'bid_offer',
                'band': 0.1,
                'elements': [
                    'G1',
                    'G2'
                ],
                'active_bid': 12.0,
                'window': 30 * 60 + 90,
                'states': [None, None, 0, 'OFF'],
                'bid_offer': {
                    'period': [
                        1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15,
                        16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27,
                        28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39,
                        40, 41, 42, 43, 44, 45, 46, 47, 48
                    ],
                    'setpoint': [
                        12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12,
                        12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12,
                        12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12,
                        12, 12, 12, 12, 12, 12, 12, 12, 12
                    ]
                },
                'outage': {
                    'period': [
                        1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15,
                        16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27,
                        28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39,
                        40, 41, 42, 43, 44, 45, 46, 47, 48
                    ],
                    'setpoint': [
                        1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
                        1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
                        1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
                    ]
                }
            }
        }
    }
    m = HydraulicModel(model)
    m.solve_lp()
    results = m.lp.resultsdict
    times = results['Lake_Aniwhenua']['Level'].keys()
    level = get_samples(m, 'Lake_Aniwhenua', 'Level', times)
    g1_power = get_samples(m, 'G1', 'Power', times)
    g1_flow = get_samples(m, 'G1', 'Flow', times)
    g2_power = get_samples(m, 'G2', 'Power', times)
    g2_flow = get_samples(m, 'G2', 'Flow', times)
    station = [sum(i) for i in zip(g1_power, g2_power)]
    assert level == pytest.approx([146.6, 146.60002, 146.6031, 146.60929,
                                  146.61547, 146.62166, 146.62784, 146.63403,
                                  146.64707, 146.66011, 146.67315, 146.68619,
                                  146.69924, 146.71207, 146.71342, 146.71477,
                                  146.71428, 146.70227, 146.69009, 146.67788,
                                  146.66567, 146.65345, 146.64124, 146.62902,
                                  146.61681, 146.6046])
    assert g1_power == pytest.approx([6.8, 11.9, 11.9, 11.9, 11.9, 11.9, 11.9,
                                     6.8, 6.8, 6.8, 6.8, 6.8, 6.8, 9.12437,
                                     9.12437, 6.8, 12.8, 12.8, 12.8, 12.8,
                                     12.8, 12.8, 12.8, 12.8, 12.8, 12.8])
    assert g1_flow == pytest.approx([22.2, 42.075, 42.075, 42.075, 42.075,
                                    42.075, 42.075, 22.2, 22.2, 22.2, 22.2,
                                    22.2, 22.2, 28.01093, 28.01093, 22.2,
                                    47.7, 47.7, 47.7, 47.7, 47.7, 47.7, 47.7,
                                    47.7, 47.7, 47.7])
    assert g2_power == pytest.approx([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                                     0.0, 0.0, 0.0, 0.0, 0.0, 9.12437,
                                     9.12437, 11.44875, 12.8, 12.8, 12.8,
                                     12.8, 12.8, 12.8, 12.8, 12.8, 12.8,
                                     12.8])
    assert g2_flow == pytest.approx([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                                    0.0, 0.0, 0.0, 0.0, 0.0, 28.01093,
                                    28.01093, 39.25467, 47.7, 47.7, 47.7,
                                    47.7, 47.7, 47.7, 47.7, 47.7, 47.7, 47.7])
    assert station == pytest.approx([6.8, 11.9, 11.9, 11.9, 11.9, 11.9, 11.9,
                                    6.8, 6.8, 6.8, 6.8, 6.8, 6.8, 18.24875,
                                    18.24875, 18.24875, 25.6, 25.6, 25.6,
                                    25.6, 25.6, 25.6, 25.6, 25.6, 25.6, 25.6])
    assert m.lp.solutioncost == pytest.approx(118.16102)
    m.remove_result()


def test_lake_bidoffer_maxroc():
    """Add rate of change limit."""
    upper = TimeSeries({1522491600: 65.0, 1522492200: 65.0,
                        1522492800: 65.0, 1522493400: 65.0})
    sysinflow = TimeSeries({1522494000: 65.0})
    power1 = TimeSeries({1522492200: 6.2, 1522494000: 6.0})
    power2 = TimeSeries({1522492200: 0.2, 1522494000: 0.0})
    lake = TimeSeries(146.6)
    model = {
        'name': 'test',
        'actual_time': 1522494300,
        'time_step': 600,
        'duration': 14400,
        'tempdir': 'tmp',
        'model': {
            'System_Inflow': {
                'type': 'valve',
                'time_series': sysinflow,
                'dstnode': 'Galatea_Site',
                'state': State.FIXED
            },
            'Galatea_Site': {
                'type': 'summing'
            },
            'Upper': {
                'type': 'river',
                'time_series': upper,
                'delay': 1800,
                'srcnode': 'Galatea_Site',
                'dstnode': 'Lake_Aniwhenua'
            },
            'Lake_Aniwhenua': {
                'type': 'storage',
                'time_series': lake,
                'LV': LV,
                'costs': [
                    [146.5, 146.6, 146.8, 146.9],
                    [[100000000, 1000000], [0, 0], [1000000, 100000000]]
                ]
            },
            'G1': {
                'type': 'generator',
                'time_series': power1,
                'state': State.FREE,
                'srcnode': 'Lake_Aniwhenua',
                'ranges': [
                    [6.8, 12.8]
                ],
                'PQ': PQ
            },
            'G2': {
                'type': 'generator',
                'time_series': power2,
                'state': State.FREE,
                'srcnode': 'Lake_Aniwhenua',
                'startlimit': [1, 1200, 1000.0],
                'ranges': [
                    [0.0],
                    [6.8, 12.8]
                ],
                'PQ': PQ
            },
            'G1Change': {
                'type': 'change_cost',
                'cost': 0.0000001,
                'element': 'G1'
            },
            'G2Change': {
                'type': 'change_cost',
                'cost': 0.0000001,
                'element': 'G2'
            },
            'Delta': {
                'type': 'delta_cost',
                'cost': 0.0000001,
                'elements': ['G1', 'G2']
            },
            'LakeProfile': {
                'type': 'profile',
                'cost': 0.0001,
                'lowcost': 0.00001,
                'element': 'Lake_Aniwhenua',
                'timeofday': [
                    [0 * 3600, 146.6],
                    [2 * 3600, 146.8],
                    [4 * 3600, 146.6],
                    [6 * 3600, 146.8],
                    [8 * 3600, 146.6],
                    [10 * 3600, 146.8],
                    [12 * 3600, 146.6],
                    [14 * 3600, 146.8],
                    [16 * 3600, 146.6],
                ],
                'LV': LV
            },
            'Bid': {
                'type': 'bid_offer',
                'band': 0.1,
                'elements': [
                    'G1',
                    'G2'
                ],
                'active_bid': 12.0,
                'window': 30 * 60 + 90,
                'states': [None, None, 0, 'OFF'],
                'bid_offer': {
                    'period': [
                        1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15,
                        16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27,
                        28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39,
                        40, 41, 42, 43, 44, 45, 46, 47, 48
                    ],
                    'setpoint': [
                        12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12,
                        12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12,
                        12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12,
                        12, 12, 12, 12, 12, 12, 12, 12, 12
                    ]
                },
                'outage': {
                    'period': [
                        1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15,
                        16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27,
                        28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39,
                        40, 41, 42, 43, 44, 45, 46, 47, 48
                    ],
                    'setpoint': [
                        1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
                        1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
                        1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
                    ]
                }
            },
            'MWRate': {
                'type': 'step_cost',
                # high cost + narrow band really hurts solve time
                'cost': 1000.0,
                'band': 5.0,
                'elements': [
                    'G1',
                    'G2'
                ],
            }
        }
    }
    m = HydraulicModel(model)
    m.solve_lp()
    results = m.lp.resultsdict
    times = sorted(results['Lake_Aniwhenua']['Level'].keys())
    level = get_samples(m, 'Lake_Aniwhenua', 'Level', times)
    g1_power = get_samples(m, 'G1', 'Power', times)
    g2_power = get_samples(m, 'G2', 'Power', times)
    station = [sum(i) for i in zip(g1_power, g2_power)]
    assert level == pytest.approx([146.6, 146.60002, 146.60397, 146.61188,
                                  146.61979, 146.6277, 146.63561, 146.64351,
                                  146.6582, 146.67296, 146.68773, 146.69586,
                                  146.70391, 146.71148, 146.70948, 146.70739,
                                  146.70522, 146.69569, 146.68563, 146.67558,
                                  146.66509, 146.6546, 146.64411, 146.63362,
                                  146.62313, 146.61264])
    assert g1_power == pytest.approx([6.8, 11.9, 11.9, 11.9, 11.9, 11.9, 11.9,
                                     6.9, 6.8, 6.8, 11.8, 11.8, 12.0, 12.8,
                                     12.8, 12.8, 12.59955, 12.69955, 12.69955,
                                     12.8, 12.8, 12.8, 12.8, 12.8, 12.8,
                                     12.8])
    assert g2_power == pytest.approx([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                                     0.0, 0.0, 0.0, 0.0, 0.0, 7.19909,
                                     7.29909, 7.39909, 12.59955, 12.69955,
                                     12.69955, 12.8, 12.8, 12.8, 12.8, 12.8,
                                     12.8, 12.8])
    assert station == pytest.approx([6.8, 11.9, 11.9, 11.9, 11.9, 11.9, 11.9,
                                    6.9, 6.8, 6.8, 11.8, 11.8, 12.0, 19.99909,
                                    20.09909, 20.19909, 25.19909, 25.39909,
                                    25.39909, 25.6, 25.6, 25.6, 25.6, 25.6,
                                    25.6, 25.6])
    assert m.lp.solutioncost == pytest.approx(108.36378)
    m.remove_result()


def test_lake_minflow():
    """Add rate of change limit."""
    rainflow = TimeSeries({1522400000: 25.0})
    lower = TimeSeries({1522400000: 2.5})
    barrage = TimeSeries({1522400000: 2.5})
    sysoutflow = TimeSeries({1522400000: 7.0})
    lake = TimeSeries(146.6)
    model = {
        'name': 'test',
        'actual_time': 1522494300,
        'time_step': 600,
        'duration': 14400,
        'tempdir': 'tmp',
        'model': {
            'Rainflow': {
                'type': 'valve',
                'time_series': rainflow,
                'state': State.FIXED,
                'dstnode': 'Lake_Aniwhenua'
            },
            'Lake_Aniwhenua': {
                'type': 'storage',
                'time_series': lake,
                'LV': LV,
                'costs': [
                    [146.5, 146.6, 146.8, 146.9],
                    [[1, 0.0000001], [0, 0], [0.0000001, 1]]
                ]
            },
            'Barrage': {
                'type': 'valve',
                'time_series': barrage,
                'state': State.FREE,
                'srcnode': 'Lake_Aniwhenua',
                'dstnode': 'Barrage_Tail'
            },
            'Barrage_Tail': {
                'type': 'summing'
            },
            'Lower': {
                'type': 'river',
                'time_series': lower,
                'delay': 1800,
                'srcnode': 'Barrage_Tail',
                'dstnode': 'station_Tail',
                'limitcost': 1.0
            },
            'station_Tail': {
                'type': 'summing'
            },
            'System_Outflow': {
                'type': 'river',
                'time_series': sysoutflow,
                'delay': 600,
                'srcnode': 'station_Tail',
                'setpoint': 30,
                'lowcost': 1000000
            },
            'BarrageChange': {
                'type': 'change_cost',
                'cost': 10.0,
                'element': 'Barrage'
            },
            'Qset': {
                'type': 'cost',
                'cost': 0.1,
                'elements': [
                    'Barrage',
                ],
                'timeofday': [
                    [0, 0]
                ]
            }
        }
    }
    m = HydraulicModel(model)
    m.solve_lp()
    results = m.lp.resultsdict
    times = sorted(results['Lake_Aniwhenua']['Level'].keys())
    rainflow = get_samples(m, 'Rainflow', 'Flow', times)
    level = get_samples(m, 'Lake_Aniwhenua', 'Level', times)
    barrage = get_samples(m, 'Barrage', 'Flow', times)
    system_outflow = get_samples(m, 'System_Outflow', 'Flow_in', times)
    assert level == pytest.approx([146.6, 146.60001, 146.60388, 146.60216,
                                  146.60043, 146.59868, 146.59693, 146.59517,
                                  146.59341, 146.59166, 146.5899, 146.58815,
                                  146.58639, 146.58463, 146.58288, 146.58112,
                                  146.57937, 146.57761, 146.57585, 146.5741,
                                  146.57234, 146.57058, 146.56883, 146.56707,
                                  146.56532, 146.56356])
    assert barrage == pytest.approx([2.5, 2.5, 30.0, 30.0, 30.0, 30.0, 30.0,
                                    30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0,
                                    30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0,
                                    30.0, 30.0, 30.0, 30.0, 30.0])
    assert system_outflow == pytest.approx([2.5, 2.5, 2.5, 2.5, 2.5, 30.0,
                                           30.0, 30.0, 30.0, 30.0, 30.0, 30.0,
                                           30.0, 30.0, 30.0, 30.0, 30.0, 30.0,
                                           30.0, 30.0, 30.0, 30.0, 30.0, 30.0,
                                           30.0, 30.0])
    assert m.lp.solutioncost == pytest.approx(137500351.2)
    m.remove_result()


def test_lake_bid_minflow():
    """Add rate of change limit."""
    # Results changed slightly for this one, the overall cost was almost
    # identical so call it ok.
    upper = TimeSeries({1522494000: 65.0})
    sysinflow = TimeSeries({1522493400: 65.0})
    barrage = TimeSeries({1522494000: 2.5})
    tail = TimeSeries({1522492200: 2.5})
    sysoutflow = TimeSeries({1522494000: 7.0})
    power1 = TimeSeries({1522492200: 6.2, 1522494000: 6.0})
    power2 = TimeSeries({1522492200: 0.2, 1522494000: 0.0})
    lake = TimeSeries(146.6)
    model = {
        'name': 'test',
        'actual_time': 1522494300,
        'time_step': 1800,
        'duration': 36000,
        'tempdir': 'tmp',
        'model': {
            'System_Inflow': {
                'type': 'valve',
                'time_series': sysinflow,
                'dstnode': 'Galatea_Site',
                'state': State.FIXED
            },
            'Galatea_Site': {
                'type': 'summing'
            },
            'Upper': {
                'type': 'river',
                'time_series': upper,
                'delay': 1800,
                'srcnode': 'Galatea_Site',
                'dstnode': 'Lake_Aniwhenua',
                'history': upper
            },
            'Lake_Aniwhenua': {
                'type': 'storage',
                'time_series': lake,
                # 'low': 146.6,
                # 'high': 146.8,
                # 'limitcost': 10000.0,
                'LV': LV,
                'costs': [
                    [146.5, 146.6, 146.8, 146.9],
                    [[1, 0.0000001], [0, 0], [0.0000001, 1]]
                ]
            },
            'G1': {
                'type': 'generator',
                'time_series': power1,
                'state': State.FREE,
                'srcnode': 'Lake_Aniwhenua',
                'ranges': [
                    [6.8, 12.8]
                ],
                'PQ': PQ
            },
            'G2': {
                'type': 'generator',
                'time_series': power2,
                'state': State.FREE,
                'srcnode': 'Lake_Aniwhenua',
                'startlimit': [1, 1200, 1000.0],
                'ranges': [
                    [0.0],
                    [6.8, 12.8]
                ],
                'PQ': PQ
            },
            'Barrage': {
                'type': 'valve',
                'time_series': barrage,
                'state': State.FREE,
                'srcnode': 'Lake_Aniwhenua',
                'dstnode': 'Barrage_Tail'
            },
            'Barrage_Flow_Cost': {
                'type': 'cost',
                'cost': 10000.0,
                'measurement': 'flow',
                'elements': [
                    'Barrage',
                ],
                'timeofday': [
                    [0, 0.0],
                ]
            },
            'Barrage_Tail': {
                'type': 'summing'
            },
            'Lower': {
                'type': 'river',
                'time_series': tail,
                'delay': 1800,
                'srcnode': 'Barrage_Tail'
            },
            'System_Outflow_Consent': {
                'type': 'consent',
                'cost': 900000000,
                'elements': ['Lower', 'G1', 'G2'],
                'day': 30.0,
                'night': 30.0
            },
            'G1Change': {
                'type': 'change_cost',
                'cost': 0.1,
                'element': 'G1'
            },
            'G2Change': {
                'type': 'change_cost',
                'cost': 0.1,
                'element': 'G2'
            },
            'Delta': {
                'type': 'delta_cost',
                'cost': 0.1,
                'elements': ['G1', 'G2']
            },
            'LakeProfile': {
                'type': 'profile',
                'cost': 0.0001,
                'lowcost': 0.00001,
                'element': 'Lake_Aniwhenua',
                'timeofday': [
                    [0 * 3600, 146.6],
                    [2 * 3600, 146.8],
                    [4 * 3600, 146.6],
                    [6 * 3600, 146.8],
                    [8 * 3600, 146.6],
                    [10 * 3600, 146.8],
                    [12 * 3600, 146.6],
                    [14 * 3600, 146.8],
                    [16 * 3600, 146.6],
                ],
                'LV': LV
            },
            'Bid': {
                'type': 'bid_offer',
                'band': 0.5,
                'elements': [
                    'G1',
                    'G2'
                ],
                'active_bid': 6.9,
                'window': 90 * 60 + 90,
                'states': [None, None, 0, 'OFF'],
                'bid_offer': {
                    'period': [
                        1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15,
                        16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27,
                        28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39,
                        40, 41, 42, 43, 44, 45, 46, 47, 48
                    ],
                    'setpoint': [
                        6.9, 6.9, 6.9, 6.9, 6.9, 6.9, 6.9, 6.9, 6.9, 6.9, 6.9,
                        6.9, 6.9, 6.9, 6.9, 6.9, 6.9, 6.9, 6.9, 6.9, 6.9, 6.9,
                        6.9, 6.9, 6.9, 6.9, 6.9, 6.9, 6.9, 6.9, 6.9, 6.9, 6.9,
                        6.9, 6.9, 6.9, 6.9, 6.9, 6.9, 6.9, 6.9, 6.9, 6.9, 6.9,
                        6.9, 6.9, 6.9, 6.9
                    ]
                },
                'outage': {
                    'period': [
                        1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15,
                        16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27,
                        28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39,
                        40, 41, 42, 43, 44, 45, 46, 47, 48
                    ],
                    'setpoint': [
                        1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
                        1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
                        1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
                    ]
                }
            },
            'MWRate': {
                'type': 'step_cost',
                # high cost + narrow band really hurts solve time
                'incost': 0.1,
                'outcost': 10000,
                'band': 5.0,
                'elements': [
                    'G1',
                    'G2'
                ],
            }
        }
    }
    m = HydraulicModel(model, timeout=3600)
    m.solve_lp()
    results = m.lp.resultsdict
    times = sorted(results['Lake_Aniwhenua']['Level'].keys())
    level = get_samples(m, 'Lake_Aniwhenua', 'Level', times)
    barrage = get_samples(m, 'Barrage', 'Flow', times)
    g1_power = get_samples(m, 'G1', 'Power', times)
    g2_power = get_samples(m, 'G2', 'Power', times)
    station = [sum(i) for i in zip(g1_power, g2_power)]
    bid = list(results['Gen']['Bid'].values())
    assert level == pytest.approx([146.6, 146.60002, 146.63562, 146.67185,
                                  146.70794, 146.74997, 146.77011, 146.77912,
                                  146.76854, 146.77322, 146.77790, 146.78661,
                                  146.79532, 146.80000, 146.77782, 146.78250,
                                  146.78718, 146.80000, 146.79501, 146.79003,
                                  146.81081, 146.80000])
    assert barrage == pytest.approx([2.5, 0.0, 6.3, 6.3, 0.0, 0.0, 0.0, 0.0,
                                    0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                                    0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    assert station == pytest.approx([6.8, 7.4, 7.4, 7.4, 7.4, 12.4, 17.4,
                                    22.4, 20.0, 20.0, 18.41544, 18.41544,
                                    20.0, 24.22400, 20.0, 20.0,
                                    16.8, 19.6, 19.6, 13.6, 21.96000,
                                    21.96000])
    assert bid == pytest.approx([6.9, 6.9, 6.9, 6.9, 12.4, 17.4, 22.4, 20.0,
                                20.0, 18.41544, 18.41544, 20.0,
                                24.224, 20, 20, 16.8,
                                19.6, 19.6, 13.6, 21.96, 21.96])
    assert m.lp.solutioncost == pytest.approx(6840169735.4)
    m.remove_result()
