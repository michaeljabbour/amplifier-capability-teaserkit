"""Typed failures. Every error carries a short code, a message, and the remedy to act on."""

from __future__ import annotations


class TeaserkitError(Exception):
    """Base class. `code` is stable and machine-readable; `remedy` tells the caller what to do next."""

    code = "error"
    exit_code = 1

    def __init__(self, message: str, remedy: str = "", *, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.remedy = remedy
        self.details = details or {}

    def to_dict(self) -> dict:
        out = {"code": self.code, "message": self.message, "remedy": self.remedy}
        if self.details:
            out["details"] = self.details
        return out


class StoryboardError(TeaserkitError):
    """The storyboard file cannot be read or does not match the schema."""

    code = "storyboard_invalid"
    exit_code = 5


class StyleViolation(TeaserkitError):
    """The storyboard parses but breaks one or more style rules."""

    code = "style_violation"
    exit_code = 5


class MissingPrerequisite(TeaserkitError):
    """Something the environment must provide (ffmpeg, Chrome, the optional AI extra) is absent."""

    code = "missing_prerequisite"
    exit_code = 4


class NoProvider(TeaserkitError):
    """An AI capability was called with no model provider configured."""

    code = "no_provider"
    exit_code = 3


class LeakDetected(TeaserkitError):
    """A deny-listed string was visible on screen while recording."""

    code = "leak_detected"
    exit_code = 6


class RecordingError(TeaserkitError):
    """A step failed while driving the browser."""

    code = "recording_failed"
    exit_code = 1


class RenderError(TeaserkitError):
    """Compositing, encoding or muxing failed."""

    code = "render_failed"
    exit_code = 1
