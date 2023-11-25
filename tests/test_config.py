"""Test the config reading."""
from pymscada.config import Config


def test_Config():
    """Read config back as dictionary."""
    cfg = Config('bus.yaml')
    assert cfg['ip'] == '127.0.0.1'
    assert cfg['port'] == 1324
