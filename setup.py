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
import sys

from setuptools import setup, find_packages

py_version = sys.version_info[:2]
if py_version < (3, 4):
    raise RuntimeError('Supvisors requires Python 3.4 or later')

requires = ['supervisor >= 4.2.1', 'pyzmq >= 20.0.0']

ip_require = ['psutil >= 5.7.3']
statistics_require = ['psutil >= 5.7.3', 'matplotlib >= 3.3.3']
xml_valid_require = ['lxml >= 4.6.2']

testing_extras = ['pytest >= 2.5.2', 'pytest-cov']

here = os.path.abspath(os.path.dirname(__file__))
try:
    README = open(os.path.join(here, 'README.md')).read()
    CHANGES = open(os.path.join(here, 'CHANGES.rst')).read()
except:
    README = """Supvisors is a control system for distributed applications over multiple Supervisor instances. """
    CHANGES = ''

CLASSIFIERS = [
    "License :: OSI Approved :: Apache Software License",
    "Development Status :: 5 - Production/Stable",
    "Intended Audience :: Developers",
    "Intended Audience :: System Administrators",
    "Natural Language :: English",
    "Environment :: No Input/Output (Daemon)",
    "Operating System :: POSIX :: Linux",
    "Programming Language :: Python :: 3.6",
    "Topic :: System :: Boot",
    "Topic :: System :: Monitoring",
    "Topic :: System :: Software Distribution"
]

version_txt = os.path.join(here, 'supvisors/version.txt')
supvisors_version = open(version_txt).read().split('=')[1].strip()

dist = setup(
    name='supvisors',
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
        "CentOS 8.3"
    ],
    packages=find_packages(),
    install_requires=requires,
    extras_require={'ip_address': ip_require,
                    'statistics': statistics_require,
                    'xml_valid': xml_valid_require,
                    'all': ip_require + statistics_require + xml_valid_require,
                    'testing': testing_extras},
    include_package_data=True,
    zip_safe=False,
    namespace_packages=['supvisors'],
    test_suite="supvisors.tests",
)
