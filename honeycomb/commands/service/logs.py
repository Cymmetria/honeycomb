# -*- coding: utf-8 -*-
"""Honeycomb service logs command."""

import os
import logging
import threading

import click

from honeycomb.defs import SERVICES
from honeycomb.utils.tailer import Tailer
from honeycomb.servicemanager.defs import STDOUTLOG, LOGS_DIR

logger = logging.getLogger(__name__)


@click.command(short_help="Show logs for a daemonized service.")
@click.option("-n", "--num", type=int, default=10, help="Number of lines to read from end of file", show_default=True)
@click.option("-f", "--follow", is_flag=True, default=False, help="Follow log output")
@click.argument("services", required=True, nargs=-1)
@click.pass_context
def logs(ctx, services, num, follow):
    """Show logs of daemonized service."""
    logger.debug("running command %s (%s)", ctx.command.name, ctx.params,
                 extra={"command": ctx.command.name, "params": ctx.params})

    home = ctx.obj["HOME"]
    services_path = os.path.join(home, SERVICES)

    tail_threads = []
    for service in services:
        logpath = os.path.join(services_path, service, LOGS_DIR, STDOUTLOG)
        if os.path.exists(logpath):
            logger.debug("tailing %s", logpath)
            # TODO: Print log lines from multiple services sorted by timestamp
            t = threading.Thread(target=Tailer, kwargs={"name": service,
                                                        "nlines": num,
                                                        "filepath": logpath,
                                                        "follow": follow})
            t.daemon = True
            t.start()
            tail_threads.append(t)

    if tail_threads:
        while tail_threads[0].isAlive():
            tail_threads[0].join(0.1)
