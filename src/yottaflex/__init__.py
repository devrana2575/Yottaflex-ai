"""YottaFlex Industrial Pump, Tank, Valve and Flow Anomaly Detection Simulator."""

__version__ = "1.0.0"
__author__ = "YottaFlex Candidate"
__generator_version__ = "1.0.0"
__schema_version__ = "1.0.0"

from .config import Config
from .id_generator import IDGenerator

__all__ = ["Config", "IDGenerator", "__version__", "__generator_version__", "__schema_version__"]
