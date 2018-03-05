# -*- coding: utf-8 -*-
"""Hooneycomb defs and constants."""
from collections import namedtuple

import six

CUSTOM_SERVICES = "custom_services"
DEBUG_LOG_FILE = 'honeycomb.debug.log'

LABEL = "label"
FIELDS = "fields"
NAME = "name"
DESCRIPTION = "description"
POLICY = "policy"
PORT = "port"
WILDCARD_PORT = "*"
PROTOCOL = "protocol"
PORTS = "ports"
ALLOW_MANY = "allow_many"
CONFLICTS_WITH = "conflicts_with"
SUPPORTED_OS_FAMILIES = "supported_os_families"

FIELD_DOES_NOT_EXIST = "field {} does not exist"
SERVICE_NAME_ALREADY_USED = "Service name already used"
CUSTOM_MESSAGE_ERROR_VALIDATION = "Failed to import config. error in field {} with value {}. error message: {}"

SERVICE_CONFIG_SECTION_KEY = "service"
ALERT_CONFIG_SECTION_KEY = "event_types"
EVENT_TYPE = 'event_type'
CONFIG_FILE_NAME = "config.json"
PARAMETERS = "parameters"
MISSING_FILE_ERROR = "Missing {} file"
MALFORMED_CONFIG_FILE = "config.json is not a valid json file"

# Custom fields constants
VALUE = 'value'
DEFAULT = 'default'
TYPE = 'type'
FIELD_LABEL = 'label'
HELP_TEXT = 'help_text'
REQUIRED = 'required'
ALLOWED_KEYS = [VALUE, DEFAULT, TYPE, FIELD_LABEL, HELP_TEXT, REQUIRED]
TEXT_TYPE = 'text'
BOOLEAN_TYPE = 'boolean'
INTEGER_TYPE = 'integer'
ALLOWED_TYPES = [TEXT_TYPE, INTEGER_TYPE, BOOLEAN_TYPE]
PARAMETERS_FIELD_ERROR = "Parameters: '{}' is not a valid {}"
PARAMETERS_DEFAULT_DOESNT_MATCH_TYPE = "Parameters: Bad value for {}={} (must be {})"
PARAMETERS_REQUIRED_FIELD_MISSING = "Parameters: '{}' is missing (use --args to see all parameters)"
# error_message is also a function to calculate the error when we ran the validator_func
ConfigField = namedtuple("ConfigField", ["validator_func", "get_error_message"])

ServiceType = namedtuple("ServiceType", [ALLOW_MANY, SUPPORTED_OS_FAMILIES, PORTS, NAME, LABEL, 'alert_types'])

SERVICE_FIELDS_TO_CREATE_OBJECT = [ALLOW_MANY, SUPPORTED_OS_FAMILIES, PORTS, NAME, LABEL]

AlertType = namedtuple("AlertType", ['name', 'label', 'aggregatable', 'system_alert'])


class AbstractDefTypeMeta(type):
    """AbstractDefTypeMeta."""

    def __getitem__(self, name):
        """Override __getitem__ to use get_value_by_name."""
        return self.get_value_by_name(name)


def isnamedtupleinstance(x):
    """Check for named tuples instances."""
    t = type(x)
    b = t.__bases__
    if len(b) != 1 or b[0] != tuple:
        return False
    f = getattr(t, '_fields', None)
    if not isinstance(f, tuple):
        return False
    return all(type(n) == str for n in f)


class AbstractDefType(object):
    """AbstractDefType."""

    __metaclass__ = AbstractDefTypeMeta

    @classmethod
    def get_items(self, **kwargs):
        """get_items."""
        items = [
            (key, value) for key, value in self.__dict__.items()
            if isnamedtupleinstance(value)
        ]

        new_lst = []
        for key, value in items:
            found = True
            for kwargs_key, kwargs_value in kwargs.items():
                if getattr(value, kwargs_key) != kwargs_value:
                    found = False
                    break
            if found:
                new_lst.append((key, value))
        return new_lst

    @classmethod
    def get_keys(self, **kwargs):
        """get_keys."""
        return [key for key, value in self.get_items(**kwargs)]

    @classmethod
    def get_values(self, **kwargs):
        """get_values."""
        return [value for _, value in self.get_items(**kwargs)]

    @classmethod
    def get_choices(self, name_key, label_key, **kwargs):
        """get_choices."""
        items = self.get_items(**kwargs)
        items.sort(key=lambda x: x[0])
        return tuple([
            (getattr(value, name_key), getattr(value, label_key))
            for _, value in items])

    @classmethod
    def get_default_choices(self, **kwargs):
        """get_default_choices."""
        return self.get_choices("name", "label", **kwargs)

    @classmethod
    def get_value_by_other_value(self, value_name, value_value, value_to_get, **kwargs):
        """get_value_by_other_value."""
        for value in self.get_values(**kwargs):
            if getattr(value, value_name) == value_value:
                if value_to_get is None:
                    return value
                else:
                    return getattr(value, value_to_get)

    @classmethod
    def get_values_by_other_value(self, value_name, value_value, value_to_get, **kwargs):
        """get_values_by_other_value."""
        return [getattr(value, value_to_get)
                for value in self.get_values(**kwargs)
                if getattr(value, value_name) == value_value]

    @classmethod
    def get_value_by_name(self, name, **kwargs):
        """get_value_by_name."""
        return self.get_value_by_other_value("name", name, None, **kwargs)

    @classmethod
    def get_label_by_name(self, name, **kwargs):
        """get_label_by_name."""
        return self.get_value_by_name(name, **kwargs).label

    @classmethod
    def does_value_value_exist(self, value_name, value_value, **kwargs):
        """does_value_value_exist."""
        return value_value in [getattr(value, value_name) for value in self.get_values(**kwargs)]

    @classmethod
    def does_value_exist_for_name(self, value_value, **kwargs):
        """does_value_exist_for_name."""
        return self.does_value_value_exist("name", value_value, **kwargs)

    @classmethod
    def get_value_names(self, **kwargs):
        """get_value_names."""
        return [value.name for value in self.get_values(**kwargs)]

    @classmethod
    def get_namedtuple_by_value(self, value_name, value_value, **kwargs):
        """get_namedtuple_by_value."""
        for value in self.get_values(**kwargs):
            if getattr(value, value_name) == value_value:
                return value

    @classmethod
    def filter_by_label(self, contained_keywords):
        """filter_by_label."""
        return [
            value
            for value
            in self.get_values()
            if contained_keywords.lower() in value.label.lower()
        ]


DecoyOSFamily = namedtuple("DecoyOsFamily", ['name', 'label', 'mount_base_dir', 'ova_os_type', 'icon_url'])


class DecoyOSFamilies(AbstractDefType):
    """DecoyOSFamilies, used in config.json."""

    LINUX = DecoyOSFamily('Linux', 'Linux', 'home/user2/deployment', 1, 'ubuntu.png')
    WINDOWS = DecoyOSFamily('Windows', 'Windows', 'deployment', 74, 'windows.png')
    ALL = DecoyOSFamily('All', 'All', None, None, None)

    @classmethod
    def all_families_name(self):
        """all_families_name."""
        return self.get_value_names()


Alert = namedtuple("Alert", ['timestamp', 'end_timestamp', 'alert_type', 'status', 'is_resolved', 'severity',
                             'decoy', 'service', 'endpoint', 'breadcrumb_name', 'image_file', 'image_sha256',
                             'image_md5', 'image_path', 'cmd', 'pid', 'ppid', 'mem_dump', 'net_capture', 'uid',
                             'file_accessed', 'originating_ip', 'originating_port', 'dest_ip', 'dest_port',
                             'originating_hostname', 'originating_mac_address', 'manufacturer', 'username',
                             'password', 'password_from_breadcrumb', 'event_description', 'domain', 'address',
                             'poisoned_hostname', 'target_endpoint', 'netstat', 'process_list', 'file_list',
                             'additional_fields', 'num_aggregated_events', 'request', 'session_video',
                             'transport_protocol', 'attack_story'])

AlertField = namedtuple("AlertField", ['name',
                                       'main_name',
                                       'sub_name',
                                       'label',
                                       'is_link',
                                       'url_name',
                                       'link_display_value',
                                       'cef_field_name'])

STATUS_IGNORED = 0
STATUS_MUTED = 1
STATUS_ALERT = 2
ALERT_STATUS = ((STATUS_IGNORED, "Ignore"), (STATUS_MUTED, "Mute"), (STATUS_ALERT, "Alert"))

CEFCustomString = namedtuple("CEFCustomString", ["field_name", "field_label", "field_label_text"])


class AlertFields(AbstractDefType):
    """All available alert fields."""

    ID = AlertField('id', None, None, 'Alert ID', False, None, None, 'externalId')
    ATTACK_STORY_ID = AlertField('attack_story_id', None, None, 'Attack story ID', False, None, None, None)
    ATTACK_STORY = AlertField('attack_story', None, None, 'Attack story', False, None, None, None)
    EVENT_TYPE = AlertField('event_type', None, None, 'Event type', False, None, None, 'act')
    DECOY = AlertField('decoy', None, None, 'Decoy', False, None, None, None)
    ORIGINATING_IP = AlertField('originating_ip', None, None, 'Originating IP', False, None, None, 'src')
    ORIGINATING_PORT = AlertField('originating_port', None, None, 'Originating port', False, None, None, 'spt')
    ORIGINATING_HOSTNAME = AlertField('originating_hostname', None, None, 'Originating hostname', False, None, None,
                                      'shost')
    ORIGINATING_MAC_ADDRESS = AlertField('originating_mac_address', None, None, 'Originating MAC address', False, None,
                                         None, 'smac')
    MANUFACTURER = AlertField('manufacturer', None, None, 'Manufacturer', False, None, None, 'sourceServiceName')
    DEST_IP = AlertField('dest_ip', None, None, 'Destination IP', False, None, None, 'dst')
    DEST_PORT = AlertField('dest_port', None, None, 'Destination port', False, None, None, 'dpt')
    FILE_ACCESSED = AlertField('file_accessed', None, None, 'Filename', False, None, None, 'filePath')
    REQUEST = AlertField('request', None, None, 'HTTP request', False, None, None, 'request')
    USERNAME = AlertField('username', None, None, 'Username', False, None, None, 'duser')
    PASSWORD = AlertField('password', None, None, 'Password', False, None, None, 'dpassword')
    PASSWORD_FROM_BREADCRUMB = AlertField('password_from_breadcrumb', None, None,
                                          'Logged in with breadcrumb credentials', False, None, None,
                                          CEFCustomString("cs5", "cs5Label", "Password From Breadcrumb"))
    DOMAIN = AlertField('domain', None, None, 'Domain', False, None, None, 'deviceDnsDomain')
    EVENT_DESC = AlertField('event_description', None, None, 'Event description', False, None, None, 'msg')
    IMAGE_PATH = AlertField('image_path', None, None, 'Original executable', True, 'download_image_file',
                            'Original executable', 'filePath')
    IMAGE_FILE = AlertField('image_file', None, None, 'Image File', False, None, None, None)
    CMD = AlertField('cmd', None, None, 'Executed command', False, None, None, 'destinationServiceName')
    PID = AlertField('pid', None, None, 'pid', False, None, None, 'spid')
    PPID = AlertField('ppid', None, None, 'ppid', False, None, None, CEFCustomString("cs2", "cs2Label", "PPID"))
    UID = AlertField('uid', None, None, 'uid', False, None, None, 'duid')
    ALERT_TYPE = AlertField('alert_type', None, None, 'Alert type', False, None, None, 'app')
    MEM_DUMP = AlertField('mem_dump', None, None, 'Memory dump', True, 'download_memory_dump_file', 'Memory dump', None)
    NET_CAPTURE = AlertField('net_capture', None, None, 'Network capture', True, 'download_network_capture_file',
                             'Network capture', None)
    TIMESTAMP = AlertField('timestamp', None, None, 'Timestamp', False, None, None, 'start')
    NUM_AGGREGATED_EVENTS = AlertField('num_aggregated_events', None, None, 'Number of aggregated events', False, None,
                                       None, None)
    EVENT_DURATION = AlertField('end_timestamp', None, None, 'Event duration', False, None, None, None)
    ADDRESS = AlertField('address', None, None, 'Unsigned code virtual address', False, None, None, None)
    IMAGE_SHA256 = AlertField('image_sha256', None, None, 'Binary SHA-256', True, None, None, 'fileHash')
    IMAGE_MD5 = AlertField('image_md5', None, None, 'Binary MD5', False, None, None, CEFCustomString("cs1", "cs1Label",
                           "MD5"))
    SESSION_VIDEO = AlertField('session_video', None, None, 'Session video', True, 'download_session_video_file',
                               'Session video', None)
    UNIQUE_ID = AlertField('unique_id', None, None, 'Unique Id', False, None, None, None)
    CHUNK_ID = AlertField('chunk_id', None, None, 'Chunk Id', False, None, None, None)
    # decoy fields:
    DECOY_IPV4 = AlertField('decoy_ipv4', 'decoy', 'ipv4', 'Decoy IP', False, None, None, 'dst')
    DECOY_NAME = AlertField('decoy_name', 'decoy', 'name', 'Decoy name', False, None, None, 'dvchost')
    DECOY_HOSTNAME = AlertField('decoy_hostname', 'decoy', 'hostname', 'Decoy hostname', False, None, None, 'dntdom')
    DECOY_OS = AlertField('decoy_os', 'decoy', 'os_label', 'Decoy OS', False, None, None, None)
    # property fields:
    PRETTY_DURATION = AlertField('pretty_duration', None, None, 'Event duration', False, None, None, None)
    PRETTY_TIMESTAMP = AlertField('pretty_timestamp', None, None, 'Timestamp', False, None, None, None)
    PRETTY_END_TIMESTAMP = AlertField('pretty_end_timestamp', None, None, 'Last event timestamp',
                                      False, None, None, None)
    TOTAL_NUM_AGGREGATED_EVENTS = AlertField('total_num_aggregated_events', None, None, 'Number of aggregated events',
                                             False, None, None, None)
    # Breadcrumb fields:
    BREADCRUMB_NAME = AlertField('breadcrumb_name', 'breadcrumb', 'name', 'Breadcrumb Name', False, None, None,
                                 CEFCustomString("cs3", "cs3Label", "Breadcrumb Name"))
    # Extra fields:
    MAZERUNNER_ID = AlertField('mazerunner_id', None, None, 'MazeRunner ID', False, None, None, 'deviceProduct')
    MAZERUNNER_INSTANCE_NAME = AlertField('maze_instance_name', None, None, 'Originating MazeRunner name', False, None,
                                          None, None)
    POISONED_HOSTNAME = AlertField('poisoned_hostname', None, None, 'Poisoned hostname', False, None, None, 'dhost')
    TARGET_ENDPOINT = AlertField('target_endpoint', None, None, 'Targeted endpoint', False, None, None, None)
    ADDITIONAL_FIELDS = AlertField('additional_fields', None, None, 'Additional fields', False, None, None,
                                   CEFCustomString("cs4", "cs4Label", "Additional Fields"))

    # Forensic Puller
    PROCESS_LIST = AlertField('process_list', None, None, 'Process list', True, 'download_process_list_file',
                              'Process list', None)
    NETSTAT = AlertField('netstat', None, None, 'Netstat output', True, 'download_netstat_file', 'Netstat output', None)
    FILE_LIST = AlertField('file_list', None, None, 'File list', False, None, '', None)

    TRANSPORT_PROTOCOL = AlertField('transport_protocol', None, None, 'Transport protocol', False, None, None, 'proto')
    PORT_SERVICE = AlertField('port_service', None, None, 'Port Service', False, None, None, None)

    @classmethod
    def get_is_link_by_name(cls, field_name):
        """get_is_link_by_name."""
        return cls.get_value_by_name(field_name).is_link

    @classmethod
    def get_url_name_by_name(cls, field_name):
        """get_url_name_by_name."""
        return cls.get_value_by_name(field_name).url_name

    @classmethod
    def get_link_display_value_by_name(cls, field_name):
        """get_link_display_value_by_name."""
        return cls.get_value_by_name(field_name).link_display_value

    @classmethod
    def get_sub_name_by_name(cls, field_name):
        """get_sub_name_by_name."""
        return cls.get_value_by_name(field_name).sub_name

    @classmethod
    def get_main_name_by_name(cls, field_name):
        """get_main_name_by_name."""
        return cls.get_value_by_name(field_name).main_name

    @classmethod
    def get_file_field_names(cls):
        """get_file_field_names."""
        return [
            cls.NET_CAPTURE.name,
            cls.SESSION_VIDEO.name,
            cls.MEM_DUMP.name,
            cls.IMAGE_FILE.name,
            cls.NETSTAT.name,
            cls.PROCESS_LIST.name
        ]


SERVICE_ALERT_VALIDATE_FIELDS = {
    SERVICE_CONFIG_SECTION_KEY: ConfigField(
        lambda field: True,
        lambda: FIELD_DOES_NOT_EXIST.format(SERVICE_CONFIG_SECTION_KEY)
    ),
    ALERT_CONFIG_SECTION_KEY: ConfigField(
        lambda field: True,
        lambda: FIELD_DOES_NOT_EXIST.format(ALERT_CONFIG_SECTION_KEY)
    ),
}

SERVICE_CONFIG_VALIDATE_FIELDS = {
    ALLOW_MANY: ConfigField(
        lambda value: value in [True, False],
        lambda: "allow_many must be boolean (True / False)"
    ),
    SUPPORTED_OS_FAMILIES: ConfigField(
        lambda family: family in DecoyOSFamilies.all_families_name(),
        lambda: "Operating system family must be one of the following: {}".format(
            ",".join(DecoyOSFamilies.all_families_name()))
    ),
    PORTS: ConfigField(
        lambda ports: isinstance(ports, list) and all(
            [port.get(PROTOCOL, False) in ["TCP", "UDP"] and
             (isinstance(port.get(PORT, False), int) or
             port.get(PORT, "") == WILDCARD_PORT) for port in ports]),
        lambda: 'Each used port entry must be in the following form {"%s": "TCP"/"UDP", "%s": INTEGER/"%s"}' %
        (PROTOCOL, PORT, WILDCARD_PORT)
    ),
    NAME: ConfigField(
        lambda name: isinstance(name, six.string_types),
        lambda: "Service name must be a string"
    ),
    LABEL: ConfigField(
        lambda label: isinstance(label, six.string_types),
        lambda: "Service label already used"
    ),
}

ALERT_CONFIG_VALIDATE_FIELDS = {
    NAME: ConfigField(
        lambda name: isinstance(name, six.string_types),
        lambda: "Alert name already used"
    ),
    LABEL: ConfigField(
        lambda label: isinstance(label, six.string_types),
        lambda: "Alert label already used"
    ),
    POLICY: ConfigField(
        lambda policy: isinstance(policy, six.string_types) and policy in [alert_status[1]
                                                                           for alert_status in ALERT_STATUS],
        lambda: "Alert policy must be one of the following: {}".format([x[1] for x in ALERT_STATUS])
    ),
    FIELDS: ConfigField(
        lambda fields: isinstance(fields, list) and all(
            [field in AlertFields.get_value_names() for field in fields]),
        lambda: "Alert fields must be one of the following: {}".format([AlertFields.get_value_names()])
    ),
}
