# -*- coding: utf-8 -*-
"""Honeycomb Cuckoo Integration."""
from __future__ import unicode_literals

import requests

from integrationmanager import exceptions
from integrationmanager.error_messages import TEST_CONNECTION_REQUIRED
from integrationmanager.integration_utils import BaseIntegration


class CuckooIntegration(BaseIntegration):
    """CuckooIntegration."""

    def get_instance_base_url(self, api=True):
        """get_instance_base_url."""
        is_secure = self.integration_data['secure'] if 'secure' in self.integration_data else False
        request_port = self.integration_data['api_port'] if api else self.integration_data['display_port']

        return '{}://{}:{}'.format(
            'https' if is_secure else 'http',
            self.integration_data['address'],
            request_port
        )

    def test_connection(self, data):
        """test_connection."""
        address = data.get('address', None)
        port = data.get('api_port', None)
        secure = data.get('secure', False)
        skip_cert_validation = data.get('skip_cert_validation', False)
        errors = {}

        if not address:
            errors['address'] = [TEST_CONNECTION_REQUIRED]
        if not port:
            errors['api_port'] = [TEST_CONNECTION_REQUIRED]

        if len(errors) > 0:
            return False, errors

        integration_url = '{}://{}:{}/cuckoo/status'.format('https' if secure else 'http', address, port)
        connection_error_msg = 'Test connection failed. Make sure cuckoo API is running ({})'.format(integration_url)
        try:
            integration_response = requests.get(integration_url, timeout=20.0, verify=not skip_cert_validation)
            success = True
            response = {}
            if integration_response.status_code != 200:
                success = False
                response = {'non_field_errors': [connection_error_msg]}
        except requests.ConnectionError:
            success = False
            response = {'non_field_errors': [connection_error_msg]}

        return success, response

    def send_event(self, required_alert_fields):
        """send_event."""
        self.logger.debug(required_alert_fields)
        integration_url = "{}/tasks/create/file".format(self.get_instance_base_url())
        skip_cert_validation = self.integration_data['skip_cert_validation']

        image_file_field = required_alert_fields["image_file"]

        if not image_file_field:
            raise exceptions.IntegrationMissingRequiredFieldError("Missing image_file field")

        image_file_name = image_file_field.name.split("/")[-1]
        image_file = image_file_field.read()
        files = {"file": (image_file_name, image_file)}
        response = requests.post(integration_url, files=files, verify=not skip_cert_validation)

        if response.status_code == 200:
            return response.json(), None

        raise exceptions.IntegrationSendEventError("status code: {}, content: {}"
                                                   .format(response.status_code, response.content))

    def poll_for_updates(self, integration_output_data):
        """poll_for_updates."""
        task_id = integration_output_data['task_id']
        skip_cert_validation = self.integration_data['skip_cert_validation']
        integration_url = "{}/tasks/report/{}".format(self.get_instance_base_url(), task_id)
        integration_url_json = "{}/json".format(integration_url)
        json_response = requests.get(integration_url_json, verify=not skip_cert_validation)

        if json_response.status_code != 200:
            raise exceptions.IntegrationPollEventError()

        polling_output = {
            'task_id': task_id,
            'score': json_response.json()['info']['score']
        }

        integration_url_all = "{}/all".format(integration_url)
        file_response = requests.get(integration_url_all, verify=not skip_cert_validation)

        if json_response.status_code != 200:
            raise exceptions.IntegrationPollEventError()

        return polling_output, {"content": file_response.content,
                                "file_ext": "tar",
                                "content_type": file_response.headers['Content-type'].split(";")[0]}

    def format_output_data(self, output_data):
        """format_output_data."""
        try:
            formatted_output_data = dict()

            task_id = output_data.get('task_id', None)
            display_url = '{}/analysis/{}/summary'.format(self.get_instance_base_url(False), task_id) \
                if task_id is not None else None

            formatted_output_data['task_id'] = {'display_name': 'Cuckoo task ID', 'type': 'string', 'value': task_id}
            formatted_output_data['task_url'] = {'display_name': 'Cuckoo URL', 'type': 'link', 'value': display_url}
            formatted_output_data['score'] = {'display_name': 'Score', 'type': 'string',
                                              'value': output_data.get('score', None)}

            return formatted_output_data
        except Exception:
            raise exceptions.IntegrationOutputFormatError()


IntegrationActionsClass = CuckooIntegration
