#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# ======================================================================
# Copyright 2016 Julien LE CLEACH
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ======================================================================

import os

from setuptools import setup, find_packages

requires = ['supervisor >= 4.2.4, < 4.3']

statistics_require = ['psutil >= 5.7.3', 'pyparsing >= 2.0.2, < 3', 'matplotlib >= 3.3.3']
xml_valid_require = ['lxml >= 4.6.2']
flask_require_36 = ['flask-restx == 0.5.1', 'Flask < 3', 'Werkzeug == 2.0.3']
flask_require = ['flask-restx >= 1.1.0', 'Flask < 3']
zmq_require = ['pyzmq >= 20.0.0']
websockets_require = ['websockets >= 10.2']

testing_extras = ['pytest >= 2.5.2', 'pytest-cov', 'pytest-mock', 'pytest-asyncio']

here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.md')).read()
CHANGES = open(os.path.join(here, 'CHANGES.md')).read()

CLASSIFIERS = [
    "License :: OSI Approved :: Apache Software License",
    "Development Status :: 5 - Production/Stable",
    "Intended Audience :: Developers",
    "Intended Audience :: System Administrators",
    "Natural Language :: English",
    "Environment :: No Input/Output (Daemon)",
    "Operating System :: POSIX :: Linux",
    "Programming Language :: Python :: 3.6",
    "Programming Language :: Python :: 3.7",
    "Programming Language :: Python :: 3.8",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: System :: Boot",
    "Topic :: System :: Monitoring",
    "Topic :: System :: Software Distribution"
]

version_txt = os.path.join(here, 'supvisors/version.txt')
supvisors_version = open(version_txt).read().split('=')[1].strip()

setup(name='supvisors',
      version=supvisors_version,
      description="A Control System for Distributed Applications",
      long_description=README + '\n\n' + CHANGES,
      long_description_content_type='text/markdown',
      classifiers=CLASSIFIERS,
      author="Julien Le Cléach",
      author_email="julien.6387.dev@gmail.com",
      url="https://github.com/julien6387/supvisors",
      download_url='https://github.com/julien6387/supvisors/archive/%s.tar.gz' % supvisors_version,
      platforms=[
          "Rocky 8.5"
      ],
      packages=find_packages(),
      python_requires='>=3.6',
      install_requires=requires,
      extras_require={'statistics': statistics_require,
                      'xml_valid': xml_valid_require,
                      'flask:python_version < "3.7"': flask_require_36,
                      'flask:python_version >= "3.7"': flask_require,
                      'zmq': zmq_require,
                      'ws:python_version >= "3.7"': websockets_require,
                      'all:python_version < "3.7"': statistics_require + xml_valid_require + flask_require_36 + zmq_require,
                      'all:python_version >= "3.7"': statistics_require + xml_valid_require + flask_require + zmq_require + websockets_require,
                      'testing': testing_extras},
      include_package_data=True,
      zip_safe=False,
      namespace_packages=['supvisors'],
      test_suite="supvisors.tests",
      entry_points={'console_scripts': ['supvisorsctl = supvisors.supvisorsctl:main',
                                        'supvisors_breed = supvisors.tools.breed:main',
                                        'supvisorsflask = supvisors.tools.supvisorsflask:main']}
      )
