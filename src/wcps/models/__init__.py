"""Model package — importing it registers all built-in models.

To add a new model: create ``model_<id>.py`` with a class that subclasses
``BaseModel`` and is decorated with ``@REGISTRY.register``, then import it here.
"""

from .base import REGISTRY, BaseModel  # noqa: F401
from . import model_v1  # noqa: F401  (registers v1)
from . import model_v2  # noqa: F401  (registers v2)

__all__ = ["REGISTRY", "BaseModel"]
