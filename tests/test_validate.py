"""Check the config files are valid."""
import logging
from pymscada import validate


def test_validate():
    """Test the files"""
    v, e, p = validate()
    assert p == './'
    if not v:
        logging.warning(e)
    assert v
