# -*- coding: utf-8 -*-
"""Honeycomb service show command."""

import os
import logging

import click
import requests
from requests.adapters import HTTPAdapter

from honeycomb import defs
from honeycomb.utils import plugin_utils
from honeycomb.servicemanager.registration import register_service

PKG_INFO_TEMPLATE = """Name: {name}
Installed: {installed}
Version: {commit_revision} Updated: {commit_date}
Summary: {label}
Location: {location}
Requires: {requirements}"""

logger = logging.getLogger(__name__)


@click.command(short_help="Show detailed information about a service")
@click.pass_context
@click.argument("service")
@click.option("-r", "--remote", is_flag=True, default=False, help="Show information only from remote repository")
def show(ctx, service, remote):
    """Show detailed information about a package."""
    logger.debug("running command %s (%s)", ctx.command.name, ctx.params,
                 extra={"command": ctx.command.name, "params": ctx.params})

    home = ctx.obj["HOME"]
    service_path = plugin_utils.get_plugin_path(home, defs.SERVICES, service)

    def collect_local_info(service, service_path):
        logger.debug("loading {} from {}".format(service, service_path))
        service = register_service(service_path)
        try:
            with open(os.path.join(service_path, "requirements.txt"), "r") as fh:
                info["requirements"] = " ".join(fh.readlines())
        except IOError:
            pass
        info["name"] = service.name
        info["label"] = service.label
        info["location"] = service_path

        return info

    def collect_remote_info(service):
        rsession = requests.Session()
        rsession.mount("https://", HTTPAdapter(max_retries=3))

        try:
            r = rsession.get(defs.GITHUB_RAW_URL.format(plugin_type=defs.SERVICES,
                                                        plugin=service, filename="config.json"))
            service_config = r.json()
            info["name"] = service_config[defs.SERVICE][defs.NAME]
            info["label"] = service_config[defs.SERVICE][defs.LABEL]
            info["location"] = defs.GITHUB_URL.format(plugin_type=defs.SERVICES, plugin=info["name"])
        except requests.exceptions.HTTPError as exc:
            logger.debug(str(exc), exc_info=True)
            raise click.ClickException("Cannot find package {}".format(service))
        except requests.exceptions.ConnectionError as exc:
            logger.debug(str(exc), exc_info=True)
            raise click.ClickException("Unable to reach remote repository {}".format(service))

        try:
            r = rsession.get(defs.GITHUB_RAW_URL.format(plugin_type=defs.SERVICES, plugin=info["name"],
                                                        filename="requirements.txt"))
            r.raise_for_status()
            info["requirements"] = " ".join(r.text.split("\n"))
        except requests.exceptions.HTTPError as exc:
            logger.debug(str(exc), exc_info=True)
            info["requirements"] = None
        except requests.exceptions.ConnectionError as exc:
            logger.debug(str(exc), exc_info=True)
            raise click.ClickException("Unable to reach remote repository {}".format(service))

        return info

    info = {"commit_revision": "N/A", "commit_date": "N/A", "requirements": "None"}

    if os.path.exists(service_path):
        info["installed"] = True
        if remote:
            click.secho("[*] Fetching info from online repository")
            info.update(collect_remote_info(service))
        else:
            info.update(collect_local_info(service, service_path))
    else:
        logger.debug("cannot find {} locally".format(service))
        if not remote:
            click.secho("[*] Cannot find service locally, checking online repository")
        info["installed"] = False
        info.update(collect_remote_info(service))
    logger.debug(info)
    click.secho(PKG_INFO_TEMPLATE.format(**info))
