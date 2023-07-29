"""Test misc functions."""
from pymscada.misc import find_nodes


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
