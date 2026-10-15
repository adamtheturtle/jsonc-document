"""Exercise the upstream JSON grammar corpus through the public API."""

from pathlib import Path

import pytest

from jsonc_document import JSONCDecodeError, parse

_CASES = sorted((Path(__file__).parent / "conformance").glob(pattern="*.json"))


@pytest.mark.parametrize(argnames="path", argvalues=_CASES, ids=str)
def test_conformance(path: Path) -> None:
    """Apply JSON grammar with explicit comment and duplicate-key policies."""
    source = path.read_bytes().decode(encoding="utf-8")
    accepted_comments = {
        "n_object_trailing_comment.json",
        "n_object_trailing_comment_slash_open.json",
        "n_structure_object_with_comment.json",
    }
    duplicate_keys = {
        "y_object_duplicated_key.json",
        "y_object_duplicated_key_and_value.json",
    }
    if (
        path.name.startswith("n_") and path.name not in accepted_comments
    ) or path.name in duplicate_keys:
        with pytest.raises(expected_exception=JSONCDecodeError):
            _ = parse(source=source)
        return
    document = parse(source=source)
    assert document.to_source() == source
    assert "".join(token.text for token in document.tokens) == source
    assert all(
        source[token.start : token.end] == token.text
        for token in document.tokens
    )
