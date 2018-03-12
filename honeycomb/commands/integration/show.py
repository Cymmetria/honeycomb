# -*- coding: utf-8 -*-
"""Honeycomb integration show command."""

import os
import logging

import click
import requests
from requests.adapters import HTTPAdapter

from honeycomb import defs
from honeycomb.utils import plugin_utils
from honeycomb.integrationmanager.defs import DISPLAY_NAME
from honeycomb.integrationmanager.registration import register_integration

PKG_INFO_TEMPLATE = """Name: {name}
Installed: {installed}
Version: {commit_revision} Updated: {commit_date}
Summary: {label}
Location: {location}
Requires: {requirements}"""

logger = logging.getLogger(__name__)


@click.command(short_help="Show detailed information about a integration")
@click.pass_context
@click.argument("integration")
@click.option("-r", "--remote", is_flag=True, default=False, help="Show information only from remote repository")
def show(ctx, integration, remote):
    """Show detailed information about a package."""
    logger.debug("running command %s (%s)", ctx.command.name, ctx.params,
                 extra={"command": ctx.command.name, "params": ctx.params})

    home = ctx.obj["HOME"]
    integration_path = plugin_utils.get_plugin_path(home, defs.INTEGRATIONS, integration)

    def collect_local_info(integration, integration_path):
        logger.debug("loading {} from {}".format(integration, integration_path))
        integration = register_integration(integration_path)
        try:
            with open(os.path.join(integration_path, "requirements.txt"), "r") as fh:
                info["requirements"] = " ".join(fh.readlines())
        except IOError:
            pass
        info["name"] = integration.name
        info["label"] = integration.label
        info["location"] = integration_path

        return info

    def collect_remote_info(integration):
        rsession = requests.Session()
        rsession.mount("https://", HTTPAdapter(max_retries=3))

        try:
            r = rsession.get(defs.GITHUB_RAW_URL.format(plugin_type=defs.INTEGRATIONS,
                                                        plugin=integration, filename="config.json"))
            integration_config = r.json()
            info["name"] = integration_config[DISPLAY_NAME]
            info["label"] = integration_config[defs.DESCRIPTION]
            info["location"] = defs.GITHUB_URL.format(plugin_type=defs.INTEGRATIONS, plugin=info["name"])
        except requests.exceptions.HTTPError as exc:
            logger.debug(str(exc), exc_info=True)
            raise click.ClickException("Cannot find package {}".format(integration))
        except requests.exceptions.ConnectionError as exc:
            logger.debug(str(exc), exc_info=True)
            raise click.ClickException("Unable to reach remote repository {}".format(integration))

        try:
            r = rsession.get(defs.GITHUB_RAW_URL.format(plugin_type=defs.INTEGRATIONS,
                             plugin=info["name"], filename="requirements.txt"))
            r.raise_for_status()
            info["requirements"] = " ".join(r.text.split("\n"))
        except requests.exceptions.HTTPError as exc:
            logger.debug(str(exc), exc_info=True)
            info["requirements"] = None
        except requests.exceptions.ConnectionError as exc:
            logger.debug(str(exc), exc_info=True)
            raise click.ClickException("Unable to reach remote repository {}".format(integration))

        return info

    info = {"commit_revision": "N/A", "commit_date": "N/A", "requirements": "None"}

    if os.path.exists(integration_path):
        info["installed"] = True
        if remote:
            click.secho("[*] Fetching info from online repository")
            info.update(collect_remote_info(integration))
        else:
            info.update(collect_local_info(integration, integration_path))
    else:
        logger.debug("cannot find {} locally".format(integration))
        if not remote:
            click.secho("[*] Cannot find integration locally, checking online repository")
        info["installed"] = False
        info.update(collect_remote_info(integration))
    logger.debug(info)
    click.secho(PKG_INFO_TEMPLATE.format(**info))
