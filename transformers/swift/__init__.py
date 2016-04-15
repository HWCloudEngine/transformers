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

import oslo_config.cfg
from oslo_utils import importutils

_swift_opts = [
    oslo_config.cfg.StrOpt('swift_api_class',
                           default='transformers.swift.swift.API',
                           help='The full class name of the '
                                'compute API class to use'),
]

oslo_config.cfg.CONF.register_opts(_swift_opts)


def API():
    swift_api_class = oslo_config.cfg.CONF.volume_api_class
    
    if swift_api_class is None:
        swift_api_class = 'transformers.swift.swift.API'
        
    cls = importutils.import_class(swift_api_class)
    return cls()
