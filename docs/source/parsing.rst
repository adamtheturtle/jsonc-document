Parsing contract
================

JSONC adds ``//`` line comments and ``/* ... */`` block comments to JSON.
Comments are allowed wherever JSON whitespace is allowed.
Line comments end at CR or LF, including CRLF.
U+2028 and U+2029 do not end a line comment and are allowed inside strings.
Trailing commas, unquoted names, single-quoted strings, hexadecimal numbers, ``NaN``, and ``Infinity`` are rejected.
Whitespace outside strings and comments is limited to space, tab, CR, and LF.

Duplicate object keys are rejected, including equivalent escaped spellings.
Finite numeric literals that overflow or underflow binary64 are rejected.
Negative zero is preserved.
UTF-16 surrogate pairs are combined; lone surrogates are retained for callers to apply their own Unicode policy.
Integers are arbitrary precision within the interpreter's decimal digit limit.
The nesting limit is 512 collections, enforced without recursive parsing.

Use ``tokenize(source=...)`` to inspect every token, including whitespace.
Token and node spans use half-open Unicode character offsets into the original source.
``tokenize`` validates individual tokens; ``parse`` validates the complete grammar.

``JSONCDecodeError`` provides ``reason``, ``msg``, ``doc``, ``pos``, ``lineno``, and ``colno``.
Positions refer to the original input, with one-based lines and columns and zero-based offsets.
CR, LF, and CRLF are recognized when reporting positions.

The document is a source snapshot.
``to_source()`` returns the original text; changing a returned Python collection does not edit that text.
Source editing is outside this library's API.
The implementation is independent of JSON5 and has no runtime dependencies.

Related libraries
-----------------

`jsonc-parser <https://github.com/NickolaiBeloguzov/jsonc-parser>`_ strips comments before decoding.
Its existing `comment retention request <https://github.com/NickolaiBeloguzov/jsonc-parser/issues/8>`_ describes the missing capability.
`json-with-comments <https://github.com/n-takumasa/json-with-comments>`_ can add comments when writing, but discards them when loading.
``jsonc-document`` instead exposes the original comment tokens and syntax spans for callers to apply their own attachment policies.

The grammar follows the `JSONC draft specification <https://jsonc.org/>`_ with trailing commas disabled.
The documented duplicate-key, numeric-range, and nesting policies further constrain accepted data.
