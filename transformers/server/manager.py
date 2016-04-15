# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# Copyright 2011 Justin Santa Barbara
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

import uuid
import urlparse

from oslo_config import cfg
import oslo_messaging as messaging
from oslo_concurrency import processutils
from oslo_utils import importutils

from transformers.common import log as logging
from transformers.i18n import _, _LE, _LI, _LW
from transformers.brick import base
from transformers import manager
from transformers.utils import get_root_helper
from transformers.server import rpcapi
from transformers.swift import swift
from transformers.s3 import s3

driver_opts = [
    'qcow2docker=transformers.server.manager.Qcow2_Docker',
]

_jobs = {}

CONF = cfg.CONF
#CONF.register_opts(driver_opts)

LOG = logging.getLogger(__name__)

class Convert_Base(object):
    def __init__(self, *args, **kwargs):
        self.qc_docker = base.Exec_Qcow2_Docker(get_root_helper())
        self.swift_api = swift.API()
        
    def download_from_swift(self, context, authen, path, f):
        LOG.error('download from swift')
        self.swift_api.get_object(context, authen, path, f)
        LOG.error('download from swift finish')
        
    def upload_to_swift(self, context, authen, path, f):
        LOG.error('upload to swift')
        self.swift_api.put_object(context, authen, path, f)
        LOG.error('upload to swift finish')
        
    def download_from_s3(self, context, authen, path, f):
        LOG.error('download from s3')
        container, _, object_name = path.strip('/').partition('/')
        authen = authen.split('@')
        user = authen[0].split(':')
        try:
            s3_api = s3.API(user[0], user[1], secure=False, region=authen[1])
            obj = s3_api.get_object(container, object_name)
            s3_api.download_object(obj, f)
        except Exception:
            raise
        LOG.error('download from s3 finish')
        
    def upload_to_s3(self, context, authen, path, f):
        LOG.error('upload to s3')
        container_name, _, object_name = path.strip('/').partition('/')
        authen = authen.split('@')
        user = authen[0].split(':')
        try:
            s3_api = s3.API(user[0], user[1], secure=False, region=authen[1])
            container = s3_api.get_container(container_name)
            with open(f) as ite:
                s3_api.upload_object_via_stream(ite, container, object_name)
            #s3_api.upload_object(f, container, object_name)
        except Exception:
            raise
        LOG.error('upload to s3 finish')

class Qcow2_Docker(Convert_Base):
    """Manages the running instances from creation to destruction."""

    def __init__(self, *args, **kwargs):
        """Load configuration options and connect to the hypervisor."""
        super(Qcow2_Docker, self).__init__()
    
    def image_convert(self, context, body, job_id):
        #LOG.debug("in server convert start %s self=%s body%s" % (dir(req), dir(self), dir(body)))
        try:
            registry_url = {}
            swift_url = {}
            s3_url = {}
            files = {}
            _jobs[job_id] = 'downloading'
            img = body['img']
            pieces = urlparse.urlparse(img['src_img'])
            LOG.error('%s %s %s' % (pieces.scheme, pieces.netloc, pieces.path))
            #LOG.error("%s %s" % (pieces.netloc, pieces.path))
            if 'swift' == pieces.scheme:
                uid = str(uuid.uuid4())
                img_dir = '/tmp/' + uid + '/'
                self.qc_docker.mkdir(img_dir)
                img_file = img_dir + img['des_img_name'].lower()
                self.download_from_swift(context, pieces.netloc, pieces.path, img_file)
            elif 's3' == pieces.scheme:
                uid = str(uuid.uuid4())
                img_dir = '/tmp/' + uid + '/'
                self.qc_docker.mkdir(img_dir)
                img_file = img_dir + img['des_img_name'].lower()
                self.download_from_s3(context, pieces.netloc, pieces.path, img_file)
            elif 'file' == pieces.scheme:
                img_file = img['src_img']
            else:
                return 'no file to convert'
            
            for des in img['destination']:
                if des['name'] == 'registry':
                    registry_url = des
                if des['name'] == 'swift':
                    swift_url = des
                if des['name'] == 's3':
                    s3_url = des
                else: 
                    files = des
            
            _jobs[job_id] = 'converting'
            need_save = len(swift_url) > 0 or len(s3_url) > 0
            self.qc_docker.convert(img_file, \
                        registry_url['path'] if len(registry_url) > 0 else [], \
                        img['des_img_name'].lower(), need_save)
            _jobs[job_id] = 'uploading'
            if len(swift_url) > 0:
                self.upload_to_swift(context, swift_url['netloc'], \
                                     swift_url['path'], img_file)
            if len(s3_url) > 0:
                self.upload_to_s3(context, s3_url['netloc'], \
                                     s3_url['path'], img_file)
            #rs = self.qc_docker.check_disk_exist('/dev/sda')
            rg = registry_url['path'] + '/' + img['des_img_name'] if \
                 len(registry_url) else None
            _jobs[job_id] = dict(destination=img['destination'], registry=rg)
            #return img['destination'], rg
        except Exception:
            _jobs[job_id] = 'failed'
            raise
        finally:
            if 'swift' == swift_url.get('name', None) or \
               's3' == s3_url.get('name', None):
                self.qc_docker.rmdir(img_dir)
            #del _jobs[job_id]

def _driver_dict_from_config(named_driver_config, *args, **kwargs):
    driver_convert = dict()

    for driver_str in named_driver_config:
        driver_type, _sep, driver = driver_str.partition('=')
        driver_class = importutils.import_class(driver)
        driver_convert[driver_type] = driver_class(*args, **kwargs)

    return driver_convert

class ConvertManager(manager.Manager):
    """Manages the running instances from creation to destruction."""

    target = messaging.Target(version='1.18')

    # How long to wait in seconds before re-issuing a shutdown
    # signal to a instance during power off.  The overall
    # time to wait is set by CONF.shutdown_timeout.
    SHUTDOWN_RETRY_INTERVAL = 10

    def __init__(self, *args, **kwargs):
        """Load configuration options and connect to the hypervisor."""
        #self.volume_api = volume.API()
        self.convert_managers = _driver_dict_from_config(
            driver_opts, self)
        self._last_host_check = 0
        self._last_bw_usage_poll = 0
        self._bw_usage_supported = True
        self._last_bw_usage_cell_update = 0
        self.migration_rpcapi = rpcapi.ConvertAPI()

        self._resource_tracker_dict = {}
        self._syncs_in_progress = {}
        

        super(ConvertManager, self).__init__(service_name="transformers-convert",
                                             *args, **kwargs)


    def get_all(self, context):
        LOG.debug("ConvertManager get all start")
        obj = {
            "resources": [{
                "id": "123",
                "name":"transformers-test",
            },
                           
            {
                "id": "1234",
                "name":"transformers-test2",
            }] 
        }
        return obj
    
    def img_convert(self, context, body=None, job_id=None):
        LOG.debug("in server manager convert start")
        img = body['img']
        convert_type = img['src_img_format']+img['des_img_format']
        conver_manager = self.convert_managers[convert_type]
        conver_manager.image_convert(context, body, job_id)
        LOG.debug("convert finished")
        
    def generate_job_id(self, context):
        LOG.debug("in server manager generate job id")
        return str(uuid.uuid4())
    
    def get_job_status(self, context, job_id=None):
        if job_id in _jobs:
            msg = _jobs[job_id]
            if msg not in ['downloading', 'converting', 'uploading']:
                del _jobs[job_id]
            return msg
        return 'job id %s not found' % job_id