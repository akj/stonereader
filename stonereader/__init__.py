"""StoneReader package metadata."""

from importlib.metadata import PackageNotFoundError, version


try:
    __version__: str | None = version("stonereader")
except PackageNotFoundError:
    __version__ = None
