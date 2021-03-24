# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.

import os
import sys
import django

sys.path.insert(0, os.path.abspath('../metagov'))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'metagov.settings')
os.environ.setdefault('DJANGO_SECRET_KEY', "t5y0(1hpfj2%%qrys%ro$*dfb6p$h%3t2dmag=+9o%t(=l3w#9") #test key

django.setup()

# -- Project information -----------------------------------------------------

project = 'Metagov'
copyright = '2021, The Metagovernance Project'
author = 'The Metagovernance Project'


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    'sphinx_rtd_theme',
    'sphinx.ext.autodoc',
    'sphinxcontrib_django',
    'sphinx.ext.autosectionlabel',
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = 'sphinx_rtd_theme'
html_theme_options = {}
# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']

autodoc_member_order = 'bysource'
