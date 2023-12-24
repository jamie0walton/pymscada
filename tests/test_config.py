"""Test the config reading."""
import pytest
from pymscada.config import Config, get_demo_file, get_demo_files, \
    get_pdf_files


def test_Config():
    """Read config back as dictionary."""
    cfg = Config('bus.yaml')
    assert cfg['ip'] == '127.0.0.1'
    assert cfg['port'] == 1324
    with pytest.raises(SystemExit):
        Config('no such config')


def test_demo():
    """Read demo files."""
    get_demo_file('tags.yaml')
    with pytest.raises(FileNotFoundError):
        get_demo_file('not here')
    for fh in get_demo_files():
        pass


def test_pdf():
    """Read pdf files."""
    for fh in get_pdf_files():
        assert fh.suffix == '.pdf'
