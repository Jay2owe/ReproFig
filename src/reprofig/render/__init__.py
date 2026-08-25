"""Semantic render manifests and explicit visual verification."""

from .schema import AxesSemantic, MarkSemantic, AnnotationSemantic, RenderManifest


def bind_artist(*args, **kwargs):
    from .matplotlib import bind_artist as implementation
    return implementation(*args, **kwargs)


def capture_matplotlib(*args, **kwargs):
    from .matplotlib import capture_matplotlib as implementation
    return implementation(*args, **kwargs)


__all__ = [
    "AnnotationSemantic", "AxesSemantic", "MarkSemantic", "RenderManifest",
    "bind_artist", "capture_matplotlib",
]
