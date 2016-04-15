#!/usr/bin/env python
# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.
from time import sleep

"""Starter script for Cinder OS API."""

import sys

from oslo_config import cfg
from transformers.common import log as logging

from transformers import i18n
i18n.enable_lazy()

# Need to register global_opts
from transformers.common import config  # noqa
from transformers import service
from transformers import version
from transformers import rpc
from transformers import utils


CONF = cfg.CONF

def main():
    CONF(sys.argv[1:], project='transformers',
         version=version.version_string())    
    logging.setup(CONF, "transformers")
    utils.monkey_patch()
 
    rpc.init(CONF)
    launcher = service.process_launcher()
    server = service.WSGIService('osapi_transformers')
    launcher.launch_service(server, workers=server.workers)
    launcher.wait()
