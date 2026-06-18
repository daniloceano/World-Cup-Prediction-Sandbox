"""Model package — importing it registers all built-in models.

To add a new model: create ``model_<id>.py`` with a class that subclasses
``BaseModel`` and is decorated with ``@REGISTRY.register``, then import it here.

Built-in regimes (see ``docs/materiais_metodos_modelo_agressivo_wcps.md``):
* ``standard``     — static relative strength (formerly ``v1``);
* ``conservative`` — strategic / draw-friendly regime (formerly ``v2``);
* ``aggressive``   — amplified favourite / goleada regime (new).
"""

from .base import REGISTRY, BaseModel  # noqa: F401
from . import model_standard  # noqa: F401  (registers "standard")
from . import model_conservative  # noqa: F401  (registers "conservative")
from . import model_aggressive  # noqa: F401  (registers "aggressive")

__all__ = ["REGISTRY", "BaseModel"]
