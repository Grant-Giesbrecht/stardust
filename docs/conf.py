# Configuration file for the Sphinx documentation builder.
#
# Full reference: https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys
from datetime import date

# Make the package importable for autodoc when building from a source checkout
sys.path.insert(0, os.path.abspath(".."))

try:  # prefer the installed distribution's version
    from importlib.metadata import version as _pkg_version

    release = _pkg_version("stardust-tools")
except Exception:  # not installed (e.g. plain source checkout)
    release = "0.1.0"

# -- Project information ---------------------------------------------------

project = "stardust"
author = "Grant Giesbrecht"
copyright = f"{date.today().year}, {author}"
version = ".".join(release.split(".")[:2])

# -- General configuration -------------------------------------------------

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",      # NumPy/Google style docstrings
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "myst_parser",              # write pages in Markdown
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

# -- MyST ------------------------------------------------------------------

myst_enable_extensions = [
    "colon_fence",      # ::: fenced directives
    "deflist",
    "fieldlist",
    "linkify",
    "substitution",
]
myst_heading_anchors = 3

# -- autodoc ---------------------------------------------------------------

autodoc_member_order = "bysource"
autodoc_typehints = "description"
autodoc_default_options = {
    "members": True,
    "undoc-members": False,
    "show-inheritance": True,
}
# Mock heavy/optional imports so the docs build without the full runtime stack
autodoc_mock_imports = []

# -- intersphinx -----------------------------------------------------------

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "numpy": ("https://numpy.org/doc/stable/", None),
    "h5py": ("https://docs.h5py.org/en/stable/", None),
}

# -- HTML output -----------------------------------------------------------

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
html_title = f"stardust {version}"
html_theme_options = {
    "collapse_navigation": False,
    "navigation_depth": 3,
    "titles_only": False,
}
