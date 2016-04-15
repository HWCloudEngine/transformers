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
Helper code for the iSCSI volume driver.

"""

import os
import re
import stat
import time
import uuid

import six
from oslo_config import cfg
from oslo_concurrency import processutils as putils

#from transformers.common import processutils as putils
from transformers.brick import executor
from transformers.brick import exception
from transformers.common import log as logging
from transformers import utils

# disk_data_opts = [
#     cfg.IntOpt('ibs',
#                default=1000,
#                help='read data from disk each time, unit is '),
#     cfg.IntOpt('obs ',
#                default=1000,
#                help='write data from disk each time, unit is '),    
# ]

CONF = cfg.CONF
#CONF.register_opts(disk_data_opts)

LOG = logging.getLogger(__name__)


class BaseCmd(executor.Executor):
    """shell  cmds administration.

    Base class for shell  cmds.
    """

    def __init__(self, root_helper, execute):
        super(BaseCmd, self).__init__(root_helper, execute=execute)

    def _run(self, *args, **kwargs):
        self._execute(*args, run_as_root=True, **kwargs)
        
    def check_disk_exist(self, disk_name):
        (out, err) = self._execute('ls', disk_name, run_as_root=True)
        
        return out, err
        
    def mkdir(self, d):
        (out, err) = self._execute('mkdir', '-p', d, run_as_root=True)
        return out, err
    
    def rmdir(self, d):
        (out, err) = self._execute('rm', '-rf', d, run_as_root=True)
        return out, err

class Exec_Qcow2_Docker(BaseCmd):
    
    def __init__(self, root_helper, execute=putils.execute): 
        super(Exec_Qcow2_Docker, self).__init__(root_helper, execute)
    
    def convert(self, f, regis_url, name, need_save):
        try:
            LOG.error('----1---- %s %s %s %s' % (f, regis_url, name, need_save))
            img_dir = '/tmp/' + str(uuid.uuid4()) + '/'
            self.mkdir(img_dir)
            (out, err) = utils.execute('image2docker', 'convert', f, 
                                       name, img_dir, run_as_root=True)
        except Exception:
            LOG.error('image2docker convert failed')
            raise
        finally:
            self.rmdir(img_dir)
        
        try:
            LOG.error('----2----  %s %s' % (name, regis_url))
            (out, err) = utils.execute('image2docker', 'upload', name, regis_url, run_as_root=True)
        except Exception:
            LOG.error('image2docker upload failed')
            raise
        
        if need_save:
            try:
                (out, err) = utils.execute('image2docker', 'save', f, regis_url, name, run_as_root=True)
            except Exception:
                LOG.error('image2docker save failed')
                raise