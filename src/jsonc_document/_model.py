"""Public document, token, and syntax tree models."""

import dataclasses
import enum
import json
from collections.abc import Callable
from typing import override

from jsonc_document.types import Scalar, Value


class TokenKind(enum.Enum):
    """The lexical categories retained in a document."""

    PUNCTUATION = enum.auto()
    STRING = enum.auto()
    LITERAL = enum.auto()
    NUMBER = enum.auto()
    COMMENT = enum.auto()
    WHITESPACE = enum.auto()


@dataclasses.dataclass(frozen=True, slots=True)
class Token:
    """A token's original spelling and half-open Unicode source span."""

    kind: TokenKind
    text: str
    start: int
    end: int
    value: Scalar


@dataclasses.dataclass(frozen=True, slots=True)
class Node:
    """
    A value and its syntax tree, retaining object keys in source order.

    ``children`` contains array elements or object member values.
    ``keys`` is empty for arrays and scalars. Collection delimiters are
    included in the node's half-open source span.
    """

    value: Value
    start: int
    end: int
    children: tuple["Node", ...]
    keys: tuple[Token, ...]
    commas: tuple[Token, ...]


@dataclasses.dataclass(frozen=True, slots=True)
class Document:
    """
    A parsed JSONC source snapshot with every lexical token retained.

    Mutating a returned Python collection does not rewrite source text.
    Source editing is outside the document API.
    """

    source: str
    root: Node
    tokens: tuple[Token, ...]

    @property
    def value(self) -> Value:
        """Return the decoded Python value."""
        return self.root.value

    @property
    def comments(self) -> tuple[Token, ...]:
        """Return line and block comments in source order."""
        return tuple(
            token for token in self.tokens if token.kind == TokenKind.COMMENT
        )

    def to_source(self) -> str:
        """Return the original source, preserving all spelling and spacing."""
        return self.source


class ErrorKind(enum.Enum):
    """Structured error categories for applications adapting
    diagnostics.
    """

    SYNTAX = enum.auto()
    DUPLICATE_KEY = enum.auto()
    NUMBER_RANGE = enum.auto()
    INTEGER_DIGITS = enum.auto()
    DEPTH = enum.auto()


class JSONCDecodeError(json.JSONDecodeError):
    """
    A syntax or data-policy error with original source coordinates.

    ``pos`` is a zero-based character offset. ``lineno`` and ``colno``
    are one-based and recognize CR, LF, and CRLF.
    """

    reason: ErrorKind
    lineno: int
    colno: int
    args: tuple[object, ...]

    def __init__(
        self, *, message: str, source: str, position: int, reason: ErrorKind
    ) -> None:
        """Record a structured failure at its original source location."""
        self.reason = reason
        super().__init__(msg=message, doc=source, pos=position)
        prefix = source[:position].replace("\r\n", "\n")
        for ending in ("\r",):
            prefix = prefix.replace(ending, "\n")
        self.lineno = prefix.count("\n") + 1
        self.colno = len(prefix.rsplit(sep="\n", maxsplit=1)[-1]) + 1
        formatted = (
            f"{message}: line {self.lineno} column {self.colno} "
            f"(char {position})"
        )
        self.args = (formatted,)

    @override
    def __reduce__(
        self,
    ) -> tuple[
        Callable[..., "JSONCDecodeError"], tuple[str, str, int, ErrorKind]
    ]:
        """Retain source coordinates and reason when copying or
        serializing.
        """
        return _restore_error, (self.msg, self.doc, self.pos, self.reason)


def _restore_error(
    message: str, source: str, position: int, reason: ErrorKind
) -> JSONCDecodeError:
    """Restore a serialized exception through its keyword argument API."""
    return JSONCDecodeError(
        message=message, source=source, position=position, reason=reason
    )
