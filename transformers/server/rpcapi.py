# Copyright 2012, Intel, Inc.
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
Client side of the transformers RPC API.
"""

from oslo_config import cfg
import oslo_messaging as messaging
from oslo_serialization import jsonutils
from transformers.common import log as logging

from transformers import rpc

rpcapi_opts = [
    cfg.StrOpt('convert_topic',
               default='transformers-convert',
               help='The topic convert service node listen on'),
]

CONF = cfg.CONF
CONF.register_opts(rpcapi_opts)

LOG = logging.getLogger(__name__)

class ConvertAPI(object):
    '''Client side of the volume rpc API.

    API version history:

        1.0 - Initial version.
    '''

    BASE_RPC_API_VERSION = '1.0'

    def __init__(self, topic=None):
        super(ConvertAPI, self).__init__()
        target = messaging.Target(topic=CONF.convert_topic,
                                  version=self.BASE_RPC_API_VERSION)
        self.client = rpc.get_client(target, '1.23', serializer=None)

    def get_all(self, ctxt):
        version = '1.18'
        #version='1.18'
        LOG.debug("convert rpc api get_all start")
        cctxt = self.client.prepare(version=version)
        return cctxt.call(ctxt, 'get_all')
    
    def img_convert(self, ctxt, body):
        LOG.debug("convert rpc api img_convert start")
        cctxt = self.client.prepare(version='1.18')
        job_id = cctxt.call(ctxt, 'generate_job_id')
        cctxt.cast(ctxt, 'img_convert', body=body, job_id=job_id)
        return job_id
    
    def get_job_status(self, ctxt, job_id):
        LOG.debug("convert rpc api get_job_status start")
        cctxt = self.client.prepare(version='1.18')
        return cctxt.call(ctxt, 'get_job_status', job_id=job_id)