# -*- coding: utf-8 -*-
"""Honeycomb generic plugin install utils."""

from __future__ import unicode_literals, absolute_import

import os
import sys
import shutil
import logging
import zipfile
import tempfile
import subprocess

import click
import requests
from requests.adapters import HTTPAdapter

from honeycomb import defs, exceptions
from honeycomb.utils import config_utils

logger = logging.getLogger(__name__)

try:
    O_BINARY = os.O_BINARY
except Exception:
    O_BINARY = 0

READ_FLAGS = os.O_RDONLY | O_BINARY
WRITE_FLAGS = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | O_BINARY
BUFFER_SIZE = 128 * 1024


class CTError(Exception):
    """Copytree exception class, used to collect errors from the recursive copy_tree function."""

    def __init__(self, errors):
        """Collect errors.

        :param errors: Collected errors
        """
        self.errors = errors


def get_plugin_path(home, plugin_type, plugin_name, editable=False):
    """Return path to plugin.

    :param home: Path to honeycomb home
    :param plugin_type: Type of plugin (:obj:`honeycomb.defs.SERVICES` pr :obj:`honeycomb.defs.INTEGRATIONS`)
    :param plugin_name: Name of plugin
    :param editable: Use plugin_name as direct path instead of loading from honeycomb home folder
    """
    if editable:
        plugin_path = plugin_name
    else:
        plugin_path = os.path.join(home, plugin_type, plugin_name)

    return os.path.realpath(plugin_path)


def install_plugin(pkgpath, plugin_type, install_path, register_func):
    """Install specified plugin.

    :param pkgpath: Name of plugin to be downloaded from online repo or path to plugin folder or zip file.
    :param install_path: Path where plugin will be installed.
    :param register_func: Method used to register and validate plugin.
    """
    service_name = os.path.basename(pkgpath)
    if os.path.exists(os.path.join(install_path, service_name)):
        raise exceptions.PluginAlreadyInstalled(pkgpath)

    if os.path.exists(pkgpath):
        logger.debug("%s exists in filesystem", pkgpath)
        if os.path.isdir(pkgpath):
            pip_status = install_dir(pkgpath, install_path, register_func)
        else:  # pkgpath is file
            pip_status = install_from_zip(pkgpath, install_path, register_func)
    else:
        logger.debug("cannot find %s locally, checking github repo", pkgpath)
        click.secho("Collecting {}..".format(pkgpath))
        pip_status = install_from_repo(pkgpath, plugin_type, install_path, register_func)

    if pip_status == 0:
        click.secho("[+] Great success!")
    else:
        # TODO: rephrase
        click.secho("[-] Service installed but something was odd with dependency install, please review debug logs")


def install_deps(pkgpath):
    """Install plugin dependencies using pip.

    We import pip here to reduce load time for when its not needed.
    """
    if os.path.exists(os.path.join(pkgpath, "requirements.txt")):
        logger.debug("installing dependencies")
        click.secho("[*] Installing dependencies")
        pipargs = ["install", "--target", os.path.join(pkgpath, defs.DEPS_DIR), "--ignore-installed",
                   "-r", os.path.join(pkgpath, "requirements.txt")]
        logger.debug("running pip %s", pipargs)
        return subprocess.check_call([sys.executable, "-m", "pip"] + pipargs)
    return 0  # pip.main returns retcode


def copy_file(src, dst):
    """Copy a single file.

    :param src: Source name
    :param dst: Destination name
    """
    try:
        fin = os.open(src, READ_FLAGS)
        stat = os.fstat(fin)
        fout = os.open(dst, WRITE_FLAGS, stat.st_mode)
        for x in iter(lambda: os.read(fin, BUFFER_SIZE), b""):
            os.write(fout, x)
    finally:
        try:
            os.close(fin)
        except Exception as exc:
            logger.debug("Failed to close file handle when copying: {}".format(exc))
        try:
            os.close(fout)
        except Exception as exc:
            logger.debug("Failed to close file handle when copying: {}".format(exc))


# Due to speed issues, shutil.copytree had to be swapped out for something faster.
# The solution was to copy (and slightly refactor) the code from:
# https://stackoverflow.com/questions/22078621/python-how-to-copy-files-fast
def copy_tree(src, dst, symlinks=False, ignore=[]):
    """Copy a full directory structure.

    :param src: Source path
    :param dst: Destination path
    :param symlinks: Copy symlinks
    :param ignore: Subdirs/filenames to ignore
    """
    names = os.listdir(src)

    if not os.path.exists(dst):
        os.makedirs(dst)
    errors = []
    for name in names:
        if name in ignore:
            continue
        srcname = os.path.join(src, name)
        dstname = os.path.join(dst, name)
        try:
            if symlinks and os.path.islink(srcname):
                linkto = os.readlink(srcname)
                os.symlink(linkto, dstname)
            elif os.path.isdir(srcname):
                copy_tree(srcname, dstname, symlinks, ignore)
            else:
                copy_file(srcname, dstname)
        except (IOError, os.error) as exc:
            errors.append((srcname, dstname, str(exc)))
        except CTError as exc:
            errors.extend(exc.errors)
    if errors:
        raise CTError(errors)


def install_dir(pkgpath, install_path, register_func, delete_after_install=False):
    """Install plugin from specified directory.

    install_path and register_func are same as :func:`install_plugin`.
    :param delete_after_install: Delete pkgpath after install (used in :func:`install_from_zip`).
    """
    logger.debug("%s is a directory, attempting to validate", pkgpath)
    plugin = register_func(pkgpath)
    logger.debug("%s looks good, copying to %s", pkgpath, install_path)
    try:
        copy_tree(pkgpath, os.path.join(install_path, plugin.name))
        if delete_after_install:
            logger.debug("deleting %s", pkgpath)
            shutil.rmtree(pkgpath)
        pkgpath = os.path.join(install_path, plugin.name)
    except (OSError, CTError) as exc:
        # TODO: handle package name exists (upgrade? overwrite?)
        logger.debug(str(exc), exc_info=True)
        raise exceptions.PluginAlreadyInstalled(plugin.name)

    return install_deps(pkgpath)


def install_from_zip(pkgpath, install_path, register_func, delete_after_install=False):
    """Install plugin from zipfile."""
    logger.debug("%s is a file, attempting to load zip", pkgpath)
    pkgtempdir = tempfile.mkdtemp(prefix="honeycomb_")
    try:
        with zipfile.ZipFile(pkgpath) as pkgzip:
            pkgzip.extractall(pkgtempdir)
    except zipfile.BadZipfile as exc:
        logger.debug(str(exc))
        raise click.ClickException(str(exc))
    if delete_after_install:
        logger.debug("deleting %s", pkgpath)
        os.remove(pkgpath)
    logger.debug("installing from unzipped folder %s", pkgtempdir)
    return install_dir(pkgtempdir, install_path, register_func, delete_after_install=True)


def install_from_repo(pkgname, plugin_type, install_path, register_func):
    """Install plugin from online repo."""
    rsession = requests.Session()
    rsession.mount("https://", HTTPAdapter(max_retries=3))

    logger.debug("trying to install %s from online repo", pkgname)
    pkgurl = "{}/{}s/{}.zip".format(defs.GITHUB_RAW, plugin_type, pkgname)
    try:
        logger.debug("Requesting HTTP HEAD: %s", pkgurl)
        r = rsession.head(pkgurl)
        r.raise_for_status()
        total_size = int(r.headers.get("content-length", 0))
        pkgsize = _sizeof_fmt(total_size)
        with click.progressbar(length=total_size, label="Downloading {} {} ({}).."
                               .format(plugin_type, pkgname, pkgsize)) as bar:
            r = rsession.get(pkgurl, stream=True)
            with tempfile.NamedTemporaryFile(delete=False) as f:
                downloaded_bytes = 0
                for chunk in r.iter_content(chunk_size=1):  # TODO: Consider increasing to reduce cycles
                    if chunk:
                        f.write(chunk)
                        downloaded_bytes += len(chunk)
                        bar.update(downloaded_bytes)
        return install_from_zip(f.name, install_path, register_func, delete_after_install=True)
    except requests.exceptions.HTTPError as exc:
        logger.debug(str(exc))
        raise exceptions.PluginNotFoundInOnlineRepo(pkgname)
    except requests.exceptions.ConnectionError as exc:
        logger.debug(str(exc))
        raise exceptions.PluginRepoConnectionError()


def _sizeof_fmt(num, suffix="B"):
    if not num:
        return "unknown size"
    for unit in ["", "K", "M", "G", "T", "P", "E", "Z"]:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s".format(num, "Yi", suffix)


def uninstall_plugin(pkgpath, force):
    """Uninstall a plugin.

    :param pkgpath: Path to package to uninstall (delete)
    :param force: Force uninstall without asking
    """
    pkgname = os.path.basename(pkgpath)
    if os.path.exists(pkgpath):
        if not force:
            click.confirm("[?] Are you sure you want to delete `{}` from honeycomb?".format(pkgname),
                          abort=True)
        try:
            shutil.rmtree(pkgpath)
            logger.debug("successfully uninstalled {}".format(pkgname))
            click.secho("[*] Uninstalled {}".format(pkgname))
        except OSError as exc:
            logger.exception(str(exc))
    else:
        click.secho("[-] doh! I cannot seem to find `{}`, are you sure it's installed?".format(pkgname))


def list_remote_plugins(installed_plugins, plugin_type):
    """List remote plugins from online repo."""
    click.secho("\n[*] Additional plugins from online repository:")
    try:
        rsession = requests.Session()
        rsession.mount("https://", HTTPAdapter(max_retries=3))

        r = rsession.get("{0}/{1}s/{1}s.txt".format(defs.GITHUB_RAW, plugin_type))
        logger.debug("fetching %ss from remote repo", plugin_type)
        plugins = [_ for _ in r.text.splitlines() if _ not in installed_plugins]
        click.secho(" ".join(plugins))

    except requests.exceptions.ConnectionError as exc:
        logger.debug(str(exc), exc_info=True)
        raise click.ClickException("Unable to fetch {} information from online repository".format(plugin_type))


def list_local_plugins(plugin_type, plugins_path, plugin_details):
    """List local plugins with details."""
    installed_plugins = list()
    for plugin in next(os.walk(plugins_path))[1]:
        s = plugin_details(plugin)
        installed_plugins.append(plugin)
        click.secho(s)

    if not installed_plugins:
        click.secho("[*] You do not have any {0}s installed, "
                    "try installing one with `honeycomb {0} install`".format(plugin_type))

    return installed_plugins


def parse_plugin_args(command_args, config_args):
    """Parse command line arguments based on the plugin's parameters config.

    :param command_args: Command line arguments as provided by the user in `key=value` format.
    :param config_args: Plugin parameters parsed from config.json.

    :returns: Validated dictionary of parameters that will be passed to plugin class
    """
    parsed_args = dict()
    for arg in command_args:
        kv = arg.split("=")
        if len(kv) != 2:
            raise click.UsageError("Invalid parameter '{}', must be in key=value format".format(arg))
        parsed_args[kv[0]] = config_utils.get_truetype(kv[1])

    for arg in config_args:
        value = arg[defs.VALUE]
        value_type = arg[defs.TYPE]
        if value in parsed_args:
            # will raise if invalid
            config_utils.validate_field_matches_type(value, parsed_args[value], value_type,
                                                     arg.get(defs.ITEMS), arg.get(defs.MIN), arg.get(defs.MAX))
        elif defs.DEFAULT in arg:  # Has a default field
            # return default values for unset parameters
            parsed_args[value] = arg[defs.DEFAULT]
        elif arg[defs.REQUIRED]:  # requires field is true
            """parameter was not supplied by user, but it's required and has no default value"""
            raise exceptions.RequiredFieldMissing(value)
    return parsed_args


def get_select_items(items):
    """Return list of possible select items."""
    option_items = list()
    for item in items:
        if isinstance(item, dict) and defs.VALUE in item and defs.LABEL in item:
            option_items.append(item[defs.VALUE])
        else:
            raise exceptions.ParametersFieldError(item, "a dictionary with {} and {}"
                                                  .format(defs.LABEL, defs.VALUE))
    return option_items


def _parse_select_options(arg):
    options = ""
    if arg[defs.TYPE] == defs.SELECT_TYPE:
        if defs.ITEMS in arg or not isinstance(arg[defs.ITEMS], list):
            option_items = get_select_items(arg[defs.ITEMS])
            options = " (valid options: {})".format(", ".join(option_items))
        else:
            raise exceptions.ParametersFieldError(defs.ITEMS, "list")

    return options


def print_plugin_args(plugin_path):
    """Print plugin parameters table."""
    args = config_utils.get_config_parameters(plugin_path)
    args_format = "{:20} {:10} {:^15} {:^10} {:25}"
    title = args_format.format(defs.NAME.upper(), defs.TYPE.upper(), defs.DEFAULT.upper(),
                               defs.REQUIRED.upper(), defs.DESCRIPTION.upper())
    click.secho(title)
    click.secho("-" * len(title))
    for arg in args:
        help_text = " ({})".format(arg[defs.HELP_TEXT]) if defs.HELP_TEXT in arg else ""
        options = _parse_select_options(arg)
        description = arg[defs.LABEL] + options + help_text
        click.secho(args_format.format(arg[defs.VALUE], arg[defs.TYPE], str(arg.get(defs.DEFAULT, None)),
                                       str(arg.get(defs.REQUIRED, False)), description))
