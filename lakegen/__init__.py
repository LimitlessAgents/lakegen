"""Lakegen: agent toolkit for lakehouse operations."""

import logging

__all__ = ["__version__"]

__version__ = "0.1.0"

# NullHandler so callers configure output; lakegen never forces a log sink.
logging.getLogger("lakegen").addHandler(logging.NullHandler())
