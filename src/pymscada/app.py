"""Standard application layer for BusClient."""
import logging
from .bus_client import BusClient


class BusApplication:
    """Bus Client application."""

    def __init__(self, name: str, config_file: str = None) -> None:
        """Create."""
        logging.info('started bus client application.')
        self.client = BusClient()
