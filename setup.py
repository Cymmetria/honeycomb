# -*- coding: utf-8 -*-
"""
Homeycomb is a honeypot framework
"""
from __future__ import absolute_import

from setuptools import find_packages, setup
from honeycomb import __version__

dependencies = ['click', 'python-daemon', 'six', 'python-json-logger', 'cefevent', 'requests']

setup(
    name='honeycomb',
    version=__version__,
    url='https://github.com/Cymmetria/honeycomb',
    license='MIT',
    author='Honeycomb - Honeypot Framework',
    author_email='omer.cohen@cymmetria.com',
    description='Homeycomb is a honeypot framework',
    long_description=__doc__,
    packages=find_packages(exclude=['tests']),
    include_package_data=True,
    zip_safe=False,
    platforms='any',
    install_requires=dependencies,
    entry_points={
        'console_scripts': [
            'honeycomb = honeycomb.scripts.cli:run_cli',
        ],
    },
    classifiers=[
        # As from http://pypi.python.org/pypi?%3Aaction=list_classifiers
        # 'Development Status :: 1 - Planning',
        # 'Development Status :: 2 - Pre-Alpha',
        # 'Development Status :: 3 - Alpha',
        'Development Status :: 4 - Beta',
        # 'Development Status :: 5 - Production/Stable',
        # 'Development Status :: 6 - Mature',
        # 'Development Status :: 7 - Inactive',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: POSIX',
        'Operating System :: MacOS',
        'Operating System :: Unix',
        'Operating System :: Microsoft :: Windows',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 3',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ]
)
