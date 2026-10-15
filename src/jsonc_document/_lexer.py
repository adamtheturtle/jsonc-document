"""JSONC lexical grammar with original source spans."""

import math
import re
from collections.abc import Iterator

from jsonc_document._model import (
    ErrorKind,
    JSONCDecodeError,
    Token,
    TokenKind,
)

_CONTROL_BOUNDARY = 0x20
_UNICODE_ESCAPE_DIGITS = 4
_WHITE_SPACE = " \t\r\n"
_NUMBER = re.compile(
    pattern=r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?"
)
_LITERAL = re.compile(pattern=r"true|false|null")
_ESCAPES = {
    '"': '"',
    "\\": "\\",
    "/": "/",
    "b": "\b",
    "f": "\f",
    "n": "\n",
    "r": "\r",
    "t": "\t",
}


def _error(*, source: str, position: int, message: str) -> JSONCDecodeError:
    """Build a position-bearing lexical error."""
    return JSONCDecodeError(
        message=message,
        source=source,
        position=position,
        reason=ErrorKind.SYNTAX,
    )


def _string(*, source: str, start: int) -> tuple[int, str]:
    """Read a double-quoted string and decode JSON escape sequences."""
    index = start + 1
    characters: list[str] = []
    while index < len(source):
        char = source[index]
        index += 1
        if char == '"':
            decoded = "".join(characters)
            return index, decoded.encode(
                encoding="utf-16", errors="surrogatepass"
            ).decode(encoding="utf-16", errors="surrogatepass")
        if ord(char) < _CONTROL_BOUNDARY:
            raise _error(
                source=source,
                position=index - 1,
                message="Unescaped control character in string",
            )
        if char != "\\":
            characters.append(char)
            continue
        if index == len(source):
            break
        char = source[index]
        index += 1
        if char == "u":
            digits = source[index : index + _UNICODE_ESCAPE_DIGITS]
            if len(digits) != _UNICODE_ESCAPE_DIGITS or any(
                digit not in "0123456789abcdefABCDEF" for digit in digits
            ):
                raise _error(
                    source=source,
                    position=index,
                    message="Invalid Unicode escape",
                )
            characters.append(chr(int(digits, base=16)))
            index += _UNICODE_ESCAPE_DIGITS
        elif char in _ESCAPES:
            characters.append(_ESCAPES[char])
        else:
            raise _error(
                source=source,
                position=index - 1,
                message="Invalid string escape",
            )
    raise _error(source=source, position=start, message="Unterminated string")


def _number_value(*, source: str, start: int, raw: str) -> int | float:
    """Decode a number while rejecting finite overflow and underflow."""
    if raw == "-0":
        return -0.0
    try:
        if not any(char in raw for char in ".eE"):
            return int(raw, base=10)
        value = float(raw)
    except ValueError as exc:
        raise JSONCDecodeError(
            source=source,
            position=start,
            reason=ErrorKind.INTEGER_DIGITS,
            message="Integer exceeds the interpreter's supported digit limit",
        ) from exc
    significant = (
        raw.lstrip("-").lower().split(sep="e")[0].replace(".", "").strip("0")
    )
    if math.isinf(value) or (value == 0 and bool(significant)):
        raise JSONCDecodeError(
            source=source,
            position=start,
            reason=ErrorKind.NUMBER_RANGE,
            message="Finite numeric token is outside binary64 range",
        )
    return value


def _block_comment_end(*, source: str, index: int) -> int:
    """Find a block comment's terminator or report its original start."""
    close = source.find("*/", index + 2)
    if close == -1:
        raise _error(
            source=source, position=index, message="Unterminated block comment"
        )
    return close + 2


def _whitespace_end(*, source: str, index: int) -> int:
    """Find the end of consecutive JSON whitespace."""
    index += 1
    while index < len(source) and source[index] in _WHITE_SPACE:
        index += 1
    return index


def _line_comment_end(*, source: str, index: int) -> int:
    """Find a CR or LF terminating a line comment."""
    index += 2
    while index < len(source) and source[index] not in "\r\n":
        index += 1
    return index


def tokenize(*, source: str) -> Iterator[Token]:
    """
    Yield every source token, including comments and whitespace.

    Lexical validity is checked; use ``parse`` to validate the complete
    document grammar.
    """
    index = 0
    while index < len(source):
        start = index
        char = source[index]
        value: str | int | float | bool | None = None
        if char in _WHITE_SPACE:
            kind = TokenKind.WHITESPACE
            index = _whitespace_end(source=source, index=index)
        elif source.startswith("//", index):
            kind = TokenKind.COMMENT
            index = _line_comment_end(source=source, index=index)
        elif source.startswith("/*", index):
            kind = TokenKind.COMMENT
            index = _block_comment_end(source=source, index=index)
        elif char in "{}[]:,":
            kind = TokenKind.PUNCTUATION
            index += 1
        elif char == '"':
            kind = TokenKind.STRING
            index, value = _string(source=source, start=start)
        elif char in "-0123456789":
            kind = TokenKind.NUMBER
            match = _NUMBER.match(string=source, pos=index)
            if match is None:
                raise _error(
                    source=source, position=start, message="Invalid number"
                )
            index = match.end()
            value = _number_value(
                source=source, start=start, raw=match.group()
            )
        else:
            kind = TokenKind.LITERAL
            match = _LITERAL.match(string=source, pos=index)
            if match is None:
                raise _error(
                    source=source,
                    position=start,
                    message="Unexpected character",
                )
            index = match.end()
            literals = {"true": True, "false": False, "null": None}
            value = literals[match.group()]
        yield Token(
            kind=kind,
            text=source[start:index],
            start=start,
            end=index,
            value=value,
        )
