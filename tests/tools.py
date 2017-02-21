# This file is part of the magento module for Tryton.
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
import os
import json
import magento
from mock import MagicMock

ROOT_JSON_FOLDER = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'json_mock'
    )

def load_json(resource, filename):
    """Reads the json file from the filesystem and returns the json loaded as
    python objects

    On filesystem, the files are kept in this format:
        json_data----
              |
            resource----
                       |
                       filename

    :param resource: The magento resource for which the file has to be
                     fetched. It is same as the folder name in which the files
                     are kept.
    :param filename: The name of the file to be fethced without `.json`
                     extension.
    :returns: Loaded json from the contents of the file read.
    """
    file_path = os.path.join(
        ROOT_JSON_FOLDER, resource, str(filename)
    ) + '.json'

    return json.loads(open(file_path).read())

def mock_customer_group_api():
    mock = MagicMock(spec=magento.CustomerGroup)
    handle = MagicMock(spec=magento.CustomerGroup)
    # handle.list.side_effect = load_json('grups', 'customer_groups')
    handle.list.return_value = load_json('grups', 'customer_groups')
    handle.__enter__.return_value = handle
    mock.return_value = handle
    return mock

def mock_region_api():
    mock = MagicMock(spec=magento.Region)
    handle = MagicMock(spec=magento.Region)
    # handle.list.side_effect = load_json('grups', 'customer_groups')
    handle.list.return_value = load_json('regions', 'regions')
    handle.__enter__.return_value = handle
    mock.return_value = handle
    return mock
