# -*- coding: utf-8 -*-
"""Honeycomb commands."""

import os
import importlib

import click

commands_list = {}
cwd = os.path.dirname(__file__)


class MyGroup(click.Group):
    """Dynamic group loader class."""

    folder = None

    def __init__(self, folder, **kwargs):
        """Create a standard group, adding the folder parameter.

        :param folder: Path to folder with command .py files
        """
        click.Group.__init__(self, **kwargs)
        self.folder = os.path.join(cwd, folder)
        self.name = folder

    def list_commands(self, ctx):
        """List commands from folder."""
        rv = []
        files = [_ for _ in next(os.walk(self.folder))[2] if not _.startswith("_") and _.endswith(".py")]
        for filename in files:
            rv.append(filename[:-3])
        rv.sort()
        return rv

    def get_command(self, ctx, name):
        """Fetch command from folder."""
        plugin = os.path.basename(self.folder)
        try:
            command = importlib.import_module("honeycomb.commands.{}.{}".format(plugin, name))
        except ImportError:
            raise click.UsageError("No such command {} {}\n\n{}".format(plugin, name, self.get_help(ctx)))
        return getattr(command, name)


for command in [_ for _ in next(os.walk(os.path.realpath(cwd)))[1]]:
    if command.startswith("_"):
        continue
    command_module = "honeycomb.commands.{}".format(command)
    commands_list[command] = MyGroup(folder=command, help=importlib.import_module(command_module).__doc__)
