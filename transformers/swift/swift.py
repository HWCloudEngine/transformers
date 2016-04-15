# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""
Handles all requests relating to volumes + cinder.
"""

import httplib
#import swiftclient
from swiftclient import client as swift_client

from oslo_config import cfg

from transformers.common import log as logging
from transformers import exception
from transformers.i18n import _
from transformers.i18n import _LW

swift_opts = [
    cfg.StrOpt('swift_user',
               default='admin',
               help='Username for connecting to swift in admin context',
               deprecated_group='DEFAULT',
               deprecated_name='swift_admin_username'),
    cfg.StrOpt('swift_password',
               default='huawei',
               help='Password for connecting to swift in admin context',
               secret=True,
               deprecated_group='DEFAULT',
               deprecated_name='swift_admin_password'),
    cfg.StrOpt('swift_authurl',
               default='http://162.3.140.21:5000/v2.0/',
               help='Authorization URL for connecting to swift in admin '
               'context',
               deprecated_group='DEFAULT',
               deprecated_name='swift_admin_auth_url'),
    cfg.StrOpt('swift_tenant_name',
               default='admin',
               help='tenant name for connecting to swift',
               deprecated_group='DEFAULT',
               deprecated_name='swift_tenant_name'),
    cfg.StrOpt('swift_region_name',
               default='RegionOne',
               help='region name for connecting to swift',
               deprecated_group='DEFAULT',
               deprecated_name='swift_region_name'),
    cfg.StrOpt('swift_container',
               default='container-1',
               help='swift container',
               deprecated_group='DEFAULT'),
    cfg.StrOpt('storage_path',
               default='/',
               help='storage path',
               deprecated_group='DEFAULT'),
    cfg.StrOpt('swift_auth_version',
               default='2',
               help='swift_auth_version',
               deprecated_group='DEFAULT'),
    cfg.StrOpt('endpoint_type',
               default='internalURL',
               help='endpoint_type',
               deprecated_group='DEFAULT'),
    cfg.BoolOpt('swift_store_create_container_on_put', default=False,
                help=_('A boolean value that determines if we create the '
                       'container if it does not exist.')),
   ]

CONF = cfg.CONF
CONF.register_opts(swift_opts, 'swift')
LOG = logging.getLogger(__name__)

chunk_size = 20 * 1024 * 1024

def swiftclient(context, authen=None):
    swift_auth_version = CONF.swift.swift_auth_version or 2
    authen = authen.split('@')
    if len(authen) == 2:
        user = authen[0].split(':')
        return swift_client.Connection(
            insecure=True,
            authurl='https://' + authen[1] + '/identity-admin/v2.0',
            user=user[0],
            key=user[2],
            auth_version=swift_auth_version,
            tenant_name=user[1],
            os_options={
                'endpoint_type': CONF.swift.endpoint_type,
                'region_name': CONF.swift.swift_region_name
        })
    return swift_client.Connection(
        insecure=True,
        authurl=CONF.swift.swift_authurl,
        user=CONF.swift.swift_user,
        key=CONF.swift.swift_password,
        auth_version=swift_auth_version,
        tenant_name=CONF.swift.swift_tenant_name,
        os_options={
            'endpoint_type': CONF.swift.endpoint_type,
            'region_name': CONF.swift.swift_region_name
        })

class API(object):
    """API for interacting with the neutron manager."""
    def __init__(self, path=None, config=None):
        self._swift_container = CONF.swift.swift_container
        self._root_path = CONF.swift.storage_path or '/'
        if not self._root_path.endswith('/'):
            self._root_path += '/'

    def _init_path(self, path=None):
        path = self._root_path + path if path else self._root_path
        # Openstack does not like paths starting with '/'
        if path:
            if path.startswith('/'):
                path = path[1:]
            if path.endswith('/'):
                path = path[:-1]
        return path
    
    def create_container_if_missing(self, context, authen=None, path=None):
        """
        Creates a missing container in Swift if the
        ``swift_store_create_container_on_put`` option is set.

        :param container: Name of container to create
        :param connection: Connection to swift service
        """
        try:
            container, _, _ = path.strip('/').partition('/')
            swiftclient(context, authen).head_container(container)
        except swift_client.ClientException as e:
            if e.http_status == httplib.NOT_FOUND:
                if CONF.swift.swift_store_create_container_on_put:
                    try:
                        msg = ("Creating swift container %(container)s" %
                               {'container': container})
                        LOG.info(msg)
                        swiftclient(context, authen).put_container(container)
                    except swift_client.ClientException as e:
                        msg = ("Failed to add container to Swift.\n"
                                 "Got error from Swift: %(e)s" % {'e': e})
                        raise
                else:
                    msg = ("The container %(container)s does not exist in "
                             "Swift. Please set the "
                             "swift_store_create_container_on_put option"
                             "to add container to Swift automatically." %
                           {'container': container})
                    raise
            else:
                raise
        return True
    
    def head_object(self, context, authen=None, path=None):
        try:
            container, _, obj_id = path.strip('/').partition('/')
            LOG.error('in head_object container=%s obj_id=%s authen=%s' % (container, obj_id, authen))
            obj_id = self._init_path(obj_id)
            swiftclient(context, authen).head_object(container, obj_id)
            return True
        except Exception:
            return False
    
    def get_object(self, context, authen=None, path=None, f=None):
        try:
            container, _, obj_id = path.strip('/').partition('/')
            LOG.error('in put_object container=%s obj_id=%s authen=%s' % (container, obj_id, authen))
            obj_id = self._init_path(obj_id)
            _, obj = swiftclient(context, authen).get_object(container, \
                                                     obj_id, \
                                                     resp_chunk_size=chunk_size)
            fp = open(f, 'w')
            for buf in obj:
                fp.write(buf)
        except Exception:
            raise IOError("Could not get content: %s" % obj_id)
        finally:
            fp.close()
    
    def put_object(self, context, authen=None, path=None, f=None):
        try:
            container, _, obj_id = path.strip('/').partition('/')
            LOG.error('in put_object container=%s obj_id=%s authen=%s' % (container, obj_id, authen))
            obj_id = self._init_path(obj_id)
            fp = open(f)
            swiftclient(context, authen).put_object(container, obj_id, fp, \
                                                   chunk_size=chunk_size)
        except Exception:
            raise IOError("Could not put content: %s" % obj_id)
        finally:
            fp.close()