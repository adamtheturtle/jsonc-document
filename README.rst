jsonc-document
==============

A typed JSONC parser that preserves comments, tokens, and source spans.
It requires Python 3.12 or newer and has no runtime dependencies.

Installation
------------

.. code-block:: console

    pip install jsonc-document

Usage
-----

.. code-block:: python

    """Parse JSONC while preserving source comments."""

    import jsonc_document

    source = '// heading\n{"count": 2}'
    document = jsonc_document.parse(source=source)
    assert document.value == {"count": 2}
    assert document.comments[0].text == "// heading"
    assert document.to_source() == source

Use ``loads(source=...)`` when only Python values are needed.
See the `documentation <https://adamtheturtle.github.io/jsonc-document/>`_ for the full API and parsing policies.
