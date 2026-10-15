"""Typed JSONC parsing with comments and original source spans."""

from jsonc_document._lexer import tokenize
from jsonc_document._model import (
    Document,
    ErrorKind,
    JSONCDecodeError,
    Node,
    Token,
    TokenKind,
)
from jsonc_document._parser import loads, parse
from jsonc_document.types import Scalar, Value

__all__ = [
    "Document",
    "ErrorKind",
    "JSONCDecodeError",
    "Node",
    "Scalar",
    "Token",
    "TokenKind",
    "Value",
    "loads",
    "parse",
    "tokenize",
]
