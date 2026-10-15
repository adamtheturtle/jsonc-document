"""Sphinx documentation configuration."""

project = "jsonc-document"
author = "Adam Dangoor"
extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.intersphinx",
    "sphinx.ext.napoleon",
    "sphinx.ext.doctest",
    "sphinxcontrib.spelling",
]
html_theme = "furo"
nitpicky = True
spelling_word_list_filename = "../../spelling_private_dict.txt"
linkcheck_retries = 5

autodoc_type_aliases = {
    "Value": "jsonc_document.types.Value",
    "Scalar": "jsonc_document.types.Scalar",
}
intersphinx_mapping = {"python": ("https://docs.python.org/3", None)}
