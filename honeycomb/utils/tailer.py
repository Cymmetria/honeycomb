# -*- coding: utf-8 -*-
"""Honeycomb service log tailer."""

import os
import sys
import time
import random
import logging

import click
from attr import attrs, attrib

logger = logging.getLogger(__name__)


@attrs
class Tailer(object):
    """Colorized file tailer.

    Print lines from a file prefixed with a colored name. Optionally continue to follow file.
    """

    name = attrib(type=str)
    filepath = attrib(type=str)

    color = attrib("", type=str)
    nlines = attrib(10, type=int)
    follow = attrib(False, type=bool)
    outfile = attrib(sys.stdout)
    sleeptime = attrib(0.5, type=int)
    show_name = attrib(True, type=bool)
    used_colors = attrib([], type=list)

    colors = attrib(["red", "green", "yellow", "magenta", "blue", "cyan"], init=False)

    def print_log(self, line):
        """Print a line from a logfile."""
        click.echo(line.replace("\n", ""), file=self.outfile)

    def print_named_log(self, line):
        """Print a line from a logfile prefixed with service name."""
        click.echo("{}: {}".format(click.style(self.name, fg=self.color), line.replace("\n", "")), file=self.outfile)

    def _print(self, line):
        if self.show_name:
            self.print_named_log(line)
        else:
            self.print_log(line)

    def follow_file(self):
        """Follow a file and send every new line to a callback."""
        logger.debug("following %s", self.filepath)
        with open(self.filepath) as fh:
            # Go to the end of file
            fh.seek(0, os.SEEK_END)

            while True:
                curr_position = fh.tell()
                line = fh.readline()
                if not line:
                    fh.seek(curr_position)
                    time.sleep(self.sleeptime)
                else:
                    self._print(line)

    def __attrs_post_init__(self):
        """Seek file from end for nlines and call printlog on them, then follow if needed."""
        logger.debug("reading %d lines from %s", self.nlines, self.filepath)

        if not self.color:
            self.color = self.colors[random.randint(0, len(self.colors) - 1)]

        with open(self.filepath) as fh:
            fh.seek(0, os.SEEK_END)
            end_position = curr_position = fh.tell()
            line_count = 0
            while curr_position >= 0:
                fh.seek(curr_position)
                next_char = fh.read(1)
                if next_char == "\n" and curr_position != end_position - 1:
                    line_count += 1
                    if line_count == self.nlines:
                        break
                curr_position -= 1

            if curr_position < 0:
                fh.seek(0)

            for line in fh.readlines():
                self._print(line)

        if self.follow:
            self.follow_file()

    def stop(self):
        """Stop follow."""
        self.running = False
