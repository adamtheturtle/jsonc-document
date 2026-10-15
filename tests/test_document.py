"""Document semantics, source metadata, and parser regressions."""

import copy
import json
import math

import pytest
from hypothesis import given, strategies

from jsonc_document import (
    Document,
    ErrorKind,
    JSONCDecodeError,
    TokenKind,
    Value,
    loads,
    parse,
    tokenize,
)


@pytest.mark.parametrize(argnames="ending", argvalues=["\n", "\r", "\r\n"])
def test_comment_terminators(ending: str) -> None:
    """A following value cannot be swallowed into a line comment."""
    source = "// heading" + ending + "[1, // note" + ending + "2\n]"
    document = parse(source=source)
    assert document.value == [1, 2]
    assert [token.text for token in document.comments] == [
        "// heading",
        "// note",
    ]
    assert document.to_source() == source


def test_source_spans_and_comments() -> None:
    """Nested nodes, member names, and comment tokens reference source."""
    source = '/* lead */ {"a": [1, /* item */ 2], "b": {}} // tail'
    document = parse(source=source)
    assert isinstance(document, Document)
    assert document.value == {"a": [1, 2], "b": {}}
    assert (
        source[document.root.start : document.root.end]
        == '{"a": [1, /* item */ 2], "b": {}}'
    )
    assert [key.value for key in document.root.keys] == ["a", "b"]
    assert [token.text for token in document.root.commas] == [","]
    array = document.root.children[0]
    assert source[array.start : array.end] == "[1, /* item */ 2]"
    assert [child.value for child in array.children] == [1, 2]
    assert [comment.kind for comment in document.comments] == [
        TokenKind.COMMENT
    ] * 3
    assert "".join(token.text for token in tokenize(source=source)) == source


@pytest.mark.parametrize(
    argnames="source",
    argvalues=["-0", "-0.0", "-0e10"],
)
def test_negative_zero(source: str) -> None:
    """Negative zero retains its sign regardless of numeric spelling."""
    value = loads(source=source)
    assert isinstance(value, float)
    assert value == 0
    assert math.copysign(1.0, value) == -1


@pytest.mark.parametrize(
    argnames=("source", "expected"),
    argvalues=[
        ("123", 123),
        ("-123", -123),
        ("0.5", 0.5),
        ("1.0e2", 100.0),
        ("0e9999", 0.0),
    ],
)
def test_numbers(source: str, expected: Value) -> None:
    """JSON decimal spellings decode accurately."""
    assert loads(source=source) == expected


@pytest.mark.parametrize(
    argnames="source", argvalues=["1e400", "-1e400", "1e-4000"]
)
def test_float_range(source: str) -> None:
    """Finite literals cannot silently overflow or underflow."""
    with pytest.raises(expected_exception=JSONCDecodeError) as caught:
        _ = loads(source=source)
    assert caught.value.reason == ErrorKind.NUMBER_RANGE


@pytest.mark.parametrize(
    argnames="source",
    argvalues=[
        '{"a":1,"a":2}',
        '{"a":1,"\\u0061":2}',
        '{"😀":1,"\\ud83d\\ude00":2}',
        '{"nested":{"a":1,"a":2}}',
    ],
)
def test_duplicate_keys(source: str) -> None:
    """Equivalent decoded keys are rejected before data is overwritten."""
    with pytest.raises(expected_exception=JSONCDecodeError) as caught:
        _ = loads(source=source)
    assert caught.value.reason == ErrorKind.DUPLICATE_KEY


@pytest.mark.parametrize(argnames="quote", argvalues=['"'])
def test_raw_unicode_string_separators(quote: str) -> None:
    """Unicode line and paragraph separators are valid inside strings."""
    assert loads(source=quote + "a\u2028b\u2029c" + quote) == "a\u2028b\u2029c"


def test_string_escapes_and_surrogates() -> None:
    """JSON escape forms and UTF-16 surrogate pairs decode correctly."""
    assert loads(source=r'"\b\f\n\r\t\/\u0042\"\\"') == '\b\f\n\r\t/B"\\'
    assert loads(source=r'"\uD83D\uDE00"') == "😀"
    assert loads(source=r'"\uD800"') == "\ud800"


@pytest.mark.parametrize(
    argnames="source",
    argvalues=[
        "",
        "// comment",
        "/*comment*/",
        "[",
        "{a",
        "{a:",
        "[1",
        "{a:1 b:2}",
        "{a 1}",
        "{1:2}",
        "[,]",
        "[1,,2]",
        "1 2",
        "undefined",
        r"\u0074rue",
        "1/2",
        "+",
        ".",
        "01",
        "0x",
        "[\u0661]",
        "'unterminated",
        '"bad\nline"',
        '"bad\rline"',
        '"\\',
        r'"\1"',
        r'"\01"',
        r'"\xG0"',
        r'"\u123"',
        r"{\x61:1}",
        r"{\u0031:1}",
        "/* unterminated",
    ],
)
def test_malformed_input(source: str) -> None:
    """Invalid syntax raises a structured source error."""
    with pytest.raises(expected_exception=JSONCDecodeError) as caught:
        _ = parse(source=source)
    error = caught.value
    assert error.reason == ErrorKind.SYNTAX
    assert error.doc == source
    assert error.pos >= 0
    assert error.lineno >= 1
    assert error.colno >= 1
    assert "line" in str(object=error)


@pytest.mark.parametrize(argnames="ending", argvalues=["\n", "\r", "\r\n"])
def test_error_locations(ending: str) -> None:
    """Coordinates reference the unchanged input and every line terminator."""
    source = "/* heading */" + ending + '{"a": 1, !}'
    with pytest.raises(expected_exception=JSONCDecodeError) as caught:
        _ = parse(source=source)
    assert caught.value.pos == source.index("!")
    assert (caught.value.lineno, caught.value.colno) == (2, 10)


def test_nesting_limit() -> None:
    """The explicit nesting limit is independent of recursive parser calls."""
    assert len(parse(source="[" * 512 + "0" + "]" * 512).root.children) == 1
    with pytest.raises(expected_exception=JSONCDecodeError) as caught:
        _ = parse(source="[" * 513 + "0" + "]" * 513)
    assert caught.value.reason == ErrorKind.DEPTH


@pytest.mark.parametrize(
    argnames="source",
    argvalues=["1" * 5000],
)
def test_integer_digit_limit(source: str) -> None:
    """Interpreter integer limits produce source-bearing typed errors."""
    with pytest.raises(expected_exception=JSONCDecodeError) as caught:
        _ = loads(source=source)
    assert caught.value.reason == ErrorKind.INTEGER_DIGITS


_JSON_SCALARS = (
    strategies.none()
    | strategies.booleans()
    | strategies.integers(min_value=-(2**63), max_value=2**63)
    | strategies.floats(allow_nan=False, allow_infinity=False)
    | strategies.text(
        alphabet=strategies.characters(exclude_categories=["Cs"])
    )
)
_JSON_VALUES = strategies.recursive(
    base=_JSON_SCALARS,
    extend=lambda children: (
        strategies.lists(elements=children, max_size=5)
        | strategies.dictionaries(
            keys=strategies.text(max_size=12), values=children, max_size=5
        )
    ),
    max_leaves=20,
)


@given(value=_JSON_VALUES)
def test_json_superset(value: Value) -> None:
    """Generated JSON values decode identically through the JSONC API."""
    source = json.dumps(obj=value)
    actual = loads(source=source)
    assert actual == value


def test_exception_copy() -> None:
    """Exceptions retain structured details across serialization
    boundaries.
    """
    with pytest.raises(expected_exception=JSONCDecodeError) as caught:
        _ = loads(source="/* heading */\r{a: !}")
    original = caught.value
    restored = copy.deepcopy(x=original)
    assert restored is not original
    assert (restored.msg, restored.doc, restored.pos, restored.reason) == (
        original.msg,
        original.doc,
        original.pos,
        original.reason,
    )
    assert str(object=restored) == str(object=original)


@pytest.mark.parametrize(
    argnames="source",
    argvalues=[
        "[1,]",
        '{"a":1,}',
        "{'a':1}",
        "{a:1}",
        "NaN",
        "Infinity",
        "-Infinity",
        "0x10",
        "+1",
        ".1",
        "1.",
        "# comment\n0",
        "[1,\ufeff2]",
        "[1,\u20032]",
        r'"\x41"',
        r'"\0"',
        r'"\v"',
        r'"\q"',
        '"a\\\nb"',
        '"\x00"',
        '"\x1f"',
        "{true:1}",
        "[1/* gap */2]",
        "tr/* gap */ue",
        "1/* gap */2",
        "[truefalse]",
    ],
)
def test_json5_extensions_rejected(source: str) -> None:
    """Only comments extend the strict JSON grammar."""
    with pytest.raises(expected_exception=JSONCDecodeError):
        _ = parse(source=source)


@pytest.mark.parametrize(argnames="separator", argvalues=["\u2028", "\u2029"])
def test_unicode_separators_in_line_comments(separator: str) -> None:
    """Unicode separators remain comment text until a CR or LF."""
    source = "// heading" + separator + "swallowed\n[1]"
    document = parse(source=source)
    assert document.value == [1]
    assert document.comments[0].text == "// heading" + separator + "swallowed"


@given(value=_JSON_VALUES)
def test_generated_commented_documents(value: Value) -> None:
    """Comments at every token boundary preserve generated JSON values."""
    tokens = list(tokenize(source=json.dumps(obj=value)))
    source = (
        "/* heading */"
        + "// note\r\n".join(
            token.text
            for token in tokens
            if token.kind != TokenKind.WHITESPACE
        )
        + "/* tail */"
    )
    document = parse(source=source)
    assert document.value == value
    assert document.to_source() == source
    assert document.comments[0].text == "/* heading */"
    assert document.comments[-1].text == "/* tail */"


def test_source_snapshot() -> None:
    """Mutating a decoded collection does not rewrite the source
    snapshot.
    """
    document = parse(source='{"a": [1]} // original')
    value = document.value
    assert isinstance(value, dict)
    value["a"] = False
    assert document.to_source() == '{"a": [1]} // original'
