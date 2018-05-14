# -*- coding: utf-8 -*-
"""Honeycomb main entry point.

This file allows running honeycomb as a module directly without calling a method
.. code-block:: bash
    $ python -m honeycomb --help
"""

from __future__ import absolute_import

import sys

from honeycomb.cli import cli


def main():
    """Provide an entry point for setup.py console_scripts."""
    return sys.exit(cli())


if __name__ == "__main__":
    main()
