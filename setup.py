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

if sys.version_info[:2] < (2, 7) or sys.version_info[0] > 2:
    msg = ("Supvisors requires Python 2.7 or later but does not work on "
           "any version of Python 3.  You are using version %s.  Please "
           "install using a supported version." % sys.version)
    sys.stderr.write(msg)
    sys.exit(1)

requires = ['supervisor >= 3.3.0', 'pyzmq >= 15.2.0']

ip_require = ['netifaces >= 0.10.4']
statistics_require = ['psutil >= 4.3.0', 'matplotlib >= 1.5.2']
xml_valid_require = ['lxml >= 3.2.1']

tests_require = ['mock >= 0.5.0']
testing_extras = tests_require + ['pytest >= 2.5.2', 'pytest-cov']

here = os.path.abspath(os.path.dirname(__file__))
try:
    README = open(os.path.join(here, 'README.rst')).read()
    CHANGES = open(os.path.join(here, 'CHANGES.txt')).read()
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
    "Programming Language :: Python :: 2.7",
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
    classifiers=CLASSIFIERS,
    author="Julien Le Cléach",
    author_email="julien.6387.dev@gmail.com",
    url="https://github.com/julien6387/supvisors",
    download_url = 'https://github.com/julien6387/supvisors/archive/0.1.tar.gz',
    platforms=[
        "CentOS 7.2"
    ],
    packages=find_packages(),
    install_requires=requires,
    extras_require={'ip_address': ip_require,
        'statistics': statistics_require,
        'xml_valid': xml_valid_require,
        'all': ip_require + statistics_require + xml_valid_require,
        'testing': testing_extras},
    tests_require=tests_require,
    include_package_data=True,
    zip_safe=False,
    namespace_packages=['supvisors'],
    test_suite="supvisors.tests",
)

