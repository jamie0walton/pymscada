"""Check the config files are valid."""
import logging
from pymscada import validate


def test_validate():
    """Test the files"""
    v, e, p = validate()
    logging.debug(f"Validation path: {p}")
    if not v:
        logging.warning(f"Validation errors: {e}")
    assert v
