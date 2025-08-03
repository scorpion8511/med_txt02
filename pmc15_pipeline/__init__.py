"""BiomedCLIP data pipeline."""

from importlib import import_module

from . import data

__all__ = ["data", "pathology_pipeline"]


def __getattr__(name):
    """Lazily import submodules when accessed."""
    if name == "pathology_pipeline":
        module = import_module(".pathology_pipeline", __name__)
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

