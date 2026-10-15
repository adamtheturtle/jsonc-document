"""An iterative JSONC parser, independent of Python's recursion limit."""

import dataclasses
import enum

from jsonc_document._lexer import tokenize
from jsonc_document._model import (
    Document,
    ErrorKind,
    JSONCDecodeError,
    Node,
    Token,
    TokenKind,
)
from jsonc_document.types import Value

_MAX_DEPTH = 512


class _State(enum.Enum):
    """The next grammar production expected inside a collection."""

    KEY = enum.auto()
    COLON = enum.auto()
    VALUE = enum.auto()
    ARRAY_VALUE = enum.auto()
    SEPARATOR = enum.auto()


@dataclasses.dataclass
class _Frame:
    """A collection currently being assembled."""

    opening: Token
    children: list[Node]
    keys: list[Token]
    commas: list[Token]
    values: dict[str, Value]
    pending_name: str
    seen_keys: set[str]
    pending_key: Token | None
    state: _State

    def expect(self, *, state: _State) -> None:
        """Record the next production expected by this frame."""
        self.state = state


@dataclasses.dataclass
class _Parser:
    """Consume syntax tokens while retaining their original positions."""

    source: str
    tokens: tuple[Token, ...]
    frames: list[_Frame]
    root: Node | None

    def error(
        self, *, token: Token, message: str, reason: ErrorKind
    ) -> JSONCDecodeError:
        """Create an error at the offending syntax token."""
        return JSONCDecodeError(
            message=message,
            source=self.source,
            position=token.start,
            reason=reason,
        )

    def accept(self, *, node: Node) -> None:
        """Attach a completed node to its parent or the document root."""
        if not bool(self.frames):
            self.root = node
            return
        frame = self.frames[-1]
        frame.children.append(node)
        if frame.pending_key is not None:
            frame.keys.append(frame.pending_key)
            frame.values[frame.pending_name] = node.value
            frame.pending_key = None
        frame.expect(state=_State.SEPARATOR)

    def close(self, *, token: Token) -> None:
        """Finish the current collection and attach its complete tree."""
        frame = self.frames.pop()
        value: Value
        if frame.opening.text == "[":
            value = [child.value for child in frame.children]
        else:
            value = frame.values
        self.accept(
            node=Node(
                value=value,
                start=frame.opening.start,
                end=token.end,
                children=tuple(frame.children),
                keys=tuple(frame.keys),
                commas=tuple(frame.commas),
            )
        )

    def advance(self, *, token: Token) -> bool:
        """Consume collection punctuation and keys before reading a
        value.
        """
        frame = self.frames[-1]
        closing = "]" if frame.opening.text == "[" else "}"
        if frame.state == _State.SEPARATOR:
            if token.text == closing:
                self.close(token=token)
            elif token.text == ",":
                frame.commas.append(token)
                frame.expect(
                    state=_State.ARRAY_VALUE if closing == "]" else _State.KEY
                )
            else:
                raise self.error(
                    token=token,
                    message="Expected comma or closing delimiter",
                    reason=ErrorKind.SYNTAX,
                )
            return True
        if (
            frame.state in {_State.KEY, _State.ARRAY_VALUE}
            and token.text == closing
        ):
            if bool(frame.commas) and len(frame.commas) == len(frame.children):
                raise self.error(
                    token=token,
                    message="Trailing commas are not allowed",
                    reason=ErrorKind.SYNTAX,
                )
            self.close(token=token)
            return True
        if frame.state == _State.KEY:
            self.read_key(token=token)
            return True
        if frame.state == _State.COLON:
            if token.text != ":":
                raise self.error(
                    token=token,
                    message="Expected colon",
                    reason=ErrorKind.SYNTAX,
                )
            frame.expect(state=_State.VALUE)
            return True
        return False

    def read_key(self, *, token: Token) -> None:
        """Decode a member name and reject repeated keys."""
        frame = self.frames[-1]
        if token.kind != TokenKind.STRING or not isinstance(token.value, str):
            raise self.error(
                token=token,
                message="Expected an object member name",
                reason=ErrorKind.SYNTAX,
            )
        if token.value in frame.seen_keys:
            raise self.error(
                token=token,
                message=f"Duplicate key {token.value!r}",
                reason=ErrorKind.DUPLICATE_KEY,
            )
        frame.seen_keys.add(token.value)
        frame.pending_key = token
        frame.pending_name = token.value
        frame.expect(state=_State.COLON)

    def read_value(self, *, token: Token) -> None:
        """Read a scalar or open another collection."""
        if token.text in {"[", "{"}:
            if len(self.frames) == _MAX_DEPTH:
                raise self.error(
                    token=token,
                    message="Input exceeds the supported nesting depth",
                    reason=ErrorKind.DEPTH,
                )
            self.frames.append(
                _Frame(
                    opening=token,
                    children=[],
                    keys=[],
                    commas=[],
                    values={},
                    pending_name="",
                    seen_keys=set(),
                    pending_key=None,
                    state=_State.ARRAY_VALUE
                    if token.text == "["
                    else _State.KEY,
                )
            )
            return
        value: Value = token.value
        if token.kind not in {
            TokenKind.NUMBER,
            TokenKind.STRING,
            TokenKind.LITERAL,
        }:
            raise self.error(
                token=token,
                message="Expected a JSONC value",
                reason=ErrorKind.SYNTAX,
            )
        self.accept(
            node=Node(
                value=value,
                start=token.start,
                end=token.end,
                children=(),
                keys=(),
                commas=(),
            )
        )

    def parse(self) -> Node:
        """Build a complete syntax tree or report the first invalid
        token.
        """
        for token in self.tokens:
            if self.root is not None and not bool(self.frames):
                raise self.error(
                    token=token,
                    message="Unexpected data after the root value",
                    reason=ErrorKind.SYNTAX,
                )
            if bool(self.frames) and self.advance(token=token):
                continue
            self.read_value(token=token)
        if self.root is None:
            message = (
                "Unterminated collection"
                if bool(self.frames)
                else "Expected a JSONC value"
            )
            raise JSONCDecodeError(
                message=message,
                source=self.source,
                position=len(self.source),
                reason=ErrorKind.SYNTAX,
            )
        return self.root


def parse(*, source: str) -> Document:
    """
    Parse a JSONC document, retaining tokens, comments, and source
    spans.

    Duplicate keys and finite numbers outside binary64 range are rejected.
    Up to 512 nested collections are accepted. No source is executed.
    """
    tokens = tuple(tokenize(source=source))
    syntax = tuple(
        token
        for token in tokens
        if token.kind not in {TokenKind.COMMENT, TokenKind.WHITESPACE}
    )
    root = _Parser(source=source, tokens=syntax, frames=[], root=None).parse()
    return Document(source=source, root=root, tokens=tokens)


def loads(*, source: str) -> Value:
    """Decode a JSONC string to ordinary Python values."""
    return parse(source=source).value
