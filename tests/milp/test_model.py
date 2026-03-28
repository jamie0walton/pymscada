"""Test low level MILP functions."""
import pytest
from pymscada.milp.model import LpModel, exact12


def test_numbers():
    """Make sure that any number to use in MILP will be 12 char long."""
    assert exact12(0.0) == "0.0000000000"
    assert exact12(1.0) == "1.0000000000"
    assert exact12(0.2) == "0.2000000000"
    assert exact12(0.002) == "0.0020000000"
    assert exact12(0.0002) == "2.000000E-04"
    assert exact12(123.456789012345678) == "123.45678901"
    assert exact12(1234567890.12345678) == "1234567890.1"
    assert exact12(12345678901.2345678) == "1.234568E+10"
    assert exact12(123456789012.345678) == "1.000000E+11"
    assert exact12(1234567890123.45678) == "1.000000E+11"
    assert exact12(-1.0) == "-1.000000000"
    assert exact12(-0.2) == "-0.200000000"
    assert exact12(-0.002) == "-0.002000000"
    assert exact12(-0.0002) == "-2.00000E-04"
    assert exact12(-123.456789012345678) == "-123.4567890"
    assert exact12(-1234567890.12345678) == "-1.23457E+09"
    assert exact12(-12345678901.2345678) == "-1.23457E+10"
    assert exact12(-123456789012.345678) == "-1.00000E+11"
    assert exact12(-1234567890123.45678) == "-1.00000E+11"


def test_model():
    """Basic check to see that the executible exists and solves."""
    m = LpModel()
    # N is the optimality test
    # N is always the last parameter
    m.add_row(-143, "x", -60, "y", "N")
    # E, G, L are = >= <=, there are no < >
    # E, G, L are always followed by a single number
    m.add_row(120, "x", 210, "y", "L", 15000)
    m.add_row(110, "x", 30, "y", "L", 4000)
    # group anything except the N or EGL and number
    m.add_row(1, ["x", "y"], "L", 75)
    m.write_mps()
    m.solve_mps()
    assert m.results["x"] == 21.875
    assert m.results["y"] == 53.125
    assert m.solutioncost == -6315.625
    m.remove_result()


def test_semi_int_limit():
    m = LpModel()
    m.add_row('x', 'N')
    m.add_limit('x', 'LI', 5.5)
    m.write_mps()
    m.solve_mps()
    assert m.results['x'] == 6.0


def test_lower_integer_limit():
    m = LpModel()
    m.add_row(-1, 'x', 'N')
    m.add_row(-1, 'x', 'y', 'E', 1.0)
    m.add_limit('y', 'UI', 41.5)
    m.write_mps()
    m.solve_mps()
    assert m.results['x'] == 40.0


def test_queens():
    n = 16

    def pos():
        for r in range(0, n):
            for c in range(0, n):
                yield f"Pos_{r}_{c}"

    def col(row):
        for c in range(0, n):
            yield f"Pos_{row}_{c}"

    def row(col):
        for r in range(0, n):
            yield f"Pos_{r}_{col}"

    def down_right(col):
        for r, c in zip(range(0, n), range(col, n)):
            yield f"Pos_{r}_{c}"

    def down_left(col):
        for r, c in zip(range(0, n), range(col, -1, -1)):
            yield f"Pos_{r}_{c}"

    def up_right(col):
        for r, c in zip(range(n - 1, 1, -1), range(col, n)):
            yield f"Pos_{r}_{c}"

    def up_left(col):
        for r, c in zip(range(n - 1, 1, -1), range(col, -1, -1)):
            yield f"Pos_{r}_{c}"

    m = LpModel()
    for i in range(0, n):
        m.add_row(col(i), 'E', 1.0)
        m.add_row(row(i), 'E', 1.0)
        m.add_row(down_right(i), 'L', 1.0)
        m.add_row(down_left(i), 'L', 1.0)
        m.add_row(up_right(i), 'L', 1.0)
        m.add_row(up_left(i), 'L', 1.0)
    for p in pos():
        m.add_limit(p, 'BV')
    m.write_mps()
    m.solve_mps()
    assert sum(m.results.values()) == pytest.approx(n)


def test_semicontinuous():
    """Test the semi-continuous range solves."""
    m = LpModel()
    m.add_row("error", "N")
    m.add_semi("G1", 1.0, 3.0)
    m.add_semi("G2", 1.0, 3.0)
    m.add_row(-1, "error", "G1", "G2", "E", 5)
    m.write_mps()
    m.solve_mps()
    assert m.results['error'] == 0.0
    assert m.results["G1"] + m.results["G2"] == 5.0
    assert m.solutioncost == 0.0
    m.remove_result()


def test_semicontinuous2():
    """Test dual range semi-continuous solves."""
    m = LpModel()
    m.add_row("error", "N")
    m.add_semi2("G1", 1.0, 3.0, 6.8, 12.8)
    m.add_semi2("G2", 1.0, 3.0, 6.8, 12.8)
    m.add_row(-1, "error", "G1", "G2", "E", 6.5)
    m.write_mps()
    m.solve_mps()
    assert m.results['error'] == 0.3
    assert m.results["G1"] + m.results["G2"] == 6.8
    assert m.solutioncost == 0.3
    m.remove_result()


def test_sos2():
    """Test special ordered set."""
    m = LpModel()
    m.add_sos2(
        'MW', [0.0, 0.00001, 6.8, 10.0, 12.8],
        'Q', [0.0, 8.0, 22.2, 30.2, 47.7]
    )
    m.add_row('MW', 'E', 2.0)
    m.write_mps()
    m.solve_mps()
    assert m.results['Q'] == 12.1764558477
    m.remove_result()


def test_sos2_cost():
    """Test piecewise linear."""
    m = LpModel()
    m.add_sos2(
        "m0", [0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
        "cost0", [1000, 1000, 0, 0, 1000, 1000]
    )
    m.add_row("m0", 'E', 0.1)
    m.add_sos2(
        "m1", [0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
        "cost1", [1000, 1000, 0, 0, 1000, 1000]
    )
    m.add_row("m1", 'E', 0.3)
    m.add_sos2(
        "m2", [0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
        "cost2", [1000, 1000, 0, 0, 1000, 1000]
    )
    m.add_row("m2", 'E', 0.5)
    m.write_mps()
    m.solve_mps()
    # cost0 solves in pre-processing so that the optimal result is found
    # yet ... not found :( ... ah well, TODO
    assert m.results['cost0'] == 1000
    assert m.results['cost1'] == 500
    assert m.results['cost2'] == 0
    m.remove_result()


def test_sos2_disc():
    """Test piecewise linear."""
    for mrl, cost in [
        [0.1, 1000],  # in high cost fixed range
        [0.3, 30],  # in low cost range
        [0.5, 0],  # in zero cost range
        [-1.0, None]  # outside of overall range, confirm infeasible
    ]:
        m = LpModel()
        m.add_sos2_disc(
            'mRL', [0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
            'cost', [[1000, 1000], [50, 10], [0, 0], [50, 10], [1000, 1000]]
        )
        m.add_row('mRL', 'E', mrl)
        m.write_mps()
        m.solve_mps()
        if cost is None:
            assert m.resultdesc == 'infeasible'
        else:
            assert m.results['cost'] == cost
        m.remove_result()


def test_integer():
    """Test integer constraint."""
    m = LpModel()
    m.add_row('error', 'N')
    m.add_row('error', 'MW', 'E', 20.0)
    m.add_limit('MW', 'UI', 12)
    m.write_mps()
    m.solve_mps()
    assert m.results['MW'] == 12.0
    m.remove_result()


def test_between():
    """Check range limit constraints."""
    m = LpModel()
    m.add_row('error', 'N')
    m.add_row('error', 'flow1', 'flow2', 'E', 100)
    m.add_row('a1', 'E', 10)
    m.add_row('b1', 'E', 30)
    m.add_between('flow1', 'a1', 'b1')
    m.add_row('a2', 'E', 30)
    m.add_row('b2', 'E', 10)
    m.add_between('flow2', 'a2', 'b2')
    m.write_mps()
    m.solve_mps()
    assert m.results['_aGTb_flow1__Unique_1__0'] == 0
    assert m.results['_aLTb_flow1__Unique_2__0'] == 1
    assert m.results['_aGTb_flow2__Unique_3__0'] == 1
    assert m.results['_aLTb_flow2__Unique_4__0'] == 0
    assert m.solutioncost == 40  # 100 - 30 flow1 - 30 flow2 = 40
    m.remove_result()
