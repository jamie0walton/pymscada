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
    r = list(find_nodes('sub', d))
    assert len(r[0].keys()) == 1
    assert r[0]['sub'] == 'here'
    assert len(r[1].keys()) == 2
    assert 'b' in r[1]
    assert r[1]['sub'] == 'there'
    assert len(r[2].keys()) == 2
    assert 'a' in r[2]
    assert r[2]['sub'] == 'and here'


def test_ramp():
    """Check ramp."""
    assert ramp(None, None, 1) is None
    assert ramp(None, 55, 1) == 55
    assert ramp(17.3, None, 1) == 17.3
    assert ramp(1, 2, 1) == 2
    assert ramp(1, 2, 0.75) == 1.75
    assert ramp(1.75, 2, 0.75) == 2
    assert ramp(2.25, 2, 0.75) == 2
