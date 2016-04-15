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
from oslo_config import cfg
from transformers.common import log as logging

from transformers.server import rpcapi
from transformers.server import manager

CONF = cfg.CONF
LOG = logging.getLogger(__name__)

class ConvertAPI(object):
    
    def __init__(self):
        
        self.convert_rpcapi = rpcapi.ConvertAPI();
        self.convert_manager = manager.ConvertManager();
        super(ConvertAPI, self).__init__()
        
    
    
    def get_all(self, context):
        LOG.debug("migration api start")
        return self.convert_rpcapi.get_all(context)
        
    def img_convert(self, context, body):
        LOG.debug("image convert start in api")
        return self.convert_rpcapi.img_convert(context, body)
    
    def get_job_status(self, context, job_id):
        LOG.debug("get_job_status start in api")
        return self.convert_rpcapi.get_job_status(context, job_id)