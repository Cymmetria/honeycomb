# -*- coding: utf-8 -*-
"""Honeycomb commands."""
from __future__ import absolute_import

from honeycomb.commands.install import install
from honeycomb.commands.list import list
from honeycomb.commands.run import run
from honeycomb.commands.show import show
from honeycomb.commands.status import status
from honeycomb.commands.stop import stop
from honeycomb.commands.test import test
from honeycomb.commands.uninstall import uninstall

commands_list = [install, uninstall, list, run, stop, show, status, test]
