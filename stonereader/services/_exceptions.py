"""Typed exceptions for the services layer.

Callers (engine, tracker, app) catch these symbols rather than hslog's own
exceptions, preserving the D-10 isolation contract.
"""
from __future__ import annotations


class ServicesError(Exception):
    """Base class for all stonereader.services errors."""


class ParserError(ServicesError):
    """Raised when the parser cannot translate a line into internal packets.

    Wraps hslog.exceptions.RegexParsingError, ParsingError, CorruptLogError.
    Watcher-level handler should log at WARNING and continue (D-04).
    """


class EngineError(ServicesError):
    """Raised when the engine cannot apply a packet to GameState.

    Most engine failures should be soft (log at WARNING and continue).
    EngineError is reserved for unrecoverable invariant violations
    (e.g. negative entity_id, mismatched controllers).
    """
