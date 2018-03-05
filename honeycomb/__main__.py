"""Honeycomb main.

This file allows runnign honeycomb as a module directly without calling a method
.. code-block:: bash
    $ python -m honeycomb --help
"""
from __future__ import absolute_import

import sys

from honeycomb import cli

if __name__ == '__main__':
    sys.exit(cli.main())
