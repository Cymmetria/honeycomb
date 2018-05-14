# -*- coding: utf-8 -*-
"""Honeycomb service models."""

from __future__ import unicode_literals, absolute_import

from attr import attrib, attrs

from honeycomb.defs import BaseNameLabel, IBaseType


@attrs
class ServiceType(object):
    """Holds loaded service metadata."""

    name = attrib(type=str)
    ports = attrib(type=list)
    label = attrib(type=str)
    allow_many = attrib(type=bool)
    supported_os_families = attrib(type=list)

    alert_types = attrib(type=list, default=[])


class OSFamilies(IBaseType):
    """Defines supported platforms for services."""

    LINUX = BaseNameLabel("Linux", "Linux")
    MACOS = BaseNameLabel("Darwin", "Darwin")
    WINDOWS = BaseNameLabel("Windows", "Windows")
    ALL = BaseNameLabel("All", "All")
