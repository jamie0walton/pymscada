"""Test misc functions."""
from pymscada.misc import find_nodes, ramp


def test_find_nodes():
    """Check the node searching tool used for TDS, and sub / pub."""
    d = {
        'a': {
            'b': {
                'sub': 'here'
            },
            'sub': 'there'
        },
        'sub': 'and here'
    }
    i = 0
    for r in find_nodes('sub', d):
        i += 1
        assert 'sub' in r
    assert i == 3


def test_ramp():
    """Check ramp."""
    assert ramp(None, None, 1) is None
    assert ramp(None, 55, 1) == 55
    assert ramp(17.3, None, 1) == 17.3
    assert ramp(1, 2, 1) == 2
    assert ramp(1, 2, 0.75) == 1.75
    assert ramp(1.75, 2, 0.75) == 2
    assert ramp(2.25, 2, 0.75) == 2
