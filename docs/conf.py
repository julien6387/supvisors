# -*- coding: utf-8 -*-
#
# Supvisors documentation build configuration file

import os
import sys
from datetime import date

# -- General configuration ------------------------------------------------

# Sphinx extension module names
extensions = ['sphinx.ext.autodoc', 'myst_parser']

# Add any paths that contain templates here, relative to this directory.
templates_path = []

# The suffix(es) of source filenames.
source_suffix = ['.rst', '.md']

# The master toctree document.
master_doc = 'index'

# General information about the project.
year = date.today().year

project = u'Supvisors'
copyright = u'2016-{}, Julien Le Cléach'.format(year)
author = u'Julien Le Cléach'

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.
#
# The Supvisors version.
parent = os.path.dirname(os.path.dirname(__file__))
sys.path.append(os.path.abspath(parent))
version_txt = os.path.join(parent, 'supvisors/version.txt')
version = release = open(version_txt).read().split('=')[1].strip()

exclude_patterns = ['.build', 'Thumbs.db', '.DS_Store']

pygments_style = 'sphinx'

# -- Options for HTML output ----------------------------------------------

# html_theme = 'sphinx_rtd_theme'
html_theme = 'renku'

html_static_path = []
