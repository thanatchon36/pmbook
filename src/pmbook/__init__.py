"""pmbook: read-only research toolkit for prediction-market order books and fills.

Research only. No account, no wallet, no funds, no orders.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("pmbook")
except PackageNotFoundError:  # pragma: no cover - running from a source tree without install
    __version__ = "0.0.0"

__all__ = ["__version__"]
