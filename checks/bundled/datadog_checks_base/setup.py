# Unless explicitly stated otherwise all files in this repository are licensed
# under the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2018 Datadog, Inc.

from setuptools import setup
from codecs import open  # To use a consistent encoding
from os import path

HERE = path.dirname(path.abspath(__file__))

# Get version info
ABOUT = {}
with open(path.join(HERE, 'datadog_checks', '__about__.py')) as f:
    exec(f.read(), ABOUT)

# Get the long description from the README file
with open(path.join(HERE, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()


setup(
    name='datadog_checks_base',
    version=ABOUT['__version__'],
    description='The Datadog Base Module (AIX)',
    long_description=long_description,
    keywords='datadog agent aix namespace',

    # The project's main homepage.
    url='https://github.com/DataDog/datadog-unix-agent',

    # Author details
    author='Datadog',
    author_email='packages@datadoghq.com',

    # License
    license='BSD',

    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'Topic :: System :: Monitoring',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
    ],

    # The package we're going to ship
    packages=['datadog_checks'],

    # Extra files to ship with the wheel package
    include_package_data=True,

    # Run-time dependencies
    # install_requires=[CHECKS_BASE_REQ],
    install_requires=[],
)
