"""Model interface and registry.

Every prediction model implements :class:`BaseModel` and registers itself with
the global :data:`REGISTRY`. The application and the ensemble only ever talk to
this interface, so adding ``v3`` / an Elo model / an xG model / an ML model is a
matter of subclassing and registering — no changes to the app layer.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from ..schemas import Prediction


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class BaseModel(ABC):
    """Common interface for all WCPS prediction models.

    Subclasses must define ``model_id`` / ``model_version`` and implement
    :meth:`predict`. ``required_inputs`` documents (for the UI and validation)
    which context blocks a model consumes.
    """

    model_id: str = "base"
    model_version: str = "0.0.0"
    display_name: str = "Base model"
    description: str = ""
    required_inputs: tuple[str, ...] = ()

    def __init__(self, config: dict[str, Any]):
        self.config = config

    @abstractmethod
    def predict(
        self,
        match: dict[str, Any],
        context: dict[str, Any] | None,
        context_ref: str | None = None,
    ) -> Prediction:
        """Return a standardized :class:`Prediction` for one match."""
        raise NotImplementedError

    # convenience for subclasses --------------------------------------------
    def _base_prediction_kwargs(
        self, match: dict[str, Any], context_ref: str | None
    ) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "model_version": self.model_version,
            "match_id": match["match_id"],
            "run_datetime": _now_iso(),
            "context_ref": context_ref,
        }


class ModelRegistry:
    """A tiny registry mapping ``model_id`` -> model class."""

    def __init__(self) -> None:
        self._models: dict[str, type[BaseModel]] = {}

    def register(self, cls: type[BaseModel]) -> type[BaseModel]:
        """Class decorator that registers a model implementation."""
        self._models[cls.model_id] = cls
        return cls

    def get(self, model_id: str) -> type[BaseModel]:
        return self._models[model_id]

    def ids(self) -> list[str]:
        return list(self._models.keys())

    def active_models(self, config: dict[str, Any]) -> list[BaseModel]:
        """Instantiate every model marked active in config (preserves order)."""
        active: list[BaseModel] = []
        for model_id, cls in self._models.items():
            section = config.get(f"model_{model_id}", {})
            if section.get("active", True):
                active.append(cls(config))
        return active


# Global registry instance.
REGISTRY = ModelRegistry()
