"""Check the config files are valid."""
from pymscada import validate


def test_validate():
    """Test the files"""
    v, e = validate()
    assert v
