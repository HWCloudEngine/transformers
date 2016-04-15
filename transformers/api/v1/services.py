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

"""The transformers api."""

import ast
import urlparse
import os

import webob
from webob import exc

from transformers.common import log as logging
from transformers.api import common
from transformers.api.wsgi import wsgi
from transformers import exception
from transformers.i18n import _, _LI
from transformers import utils

from transformers.api.views import services as services_view
from transformers.server import api as server_api
from transformers.swift import swift
from transformers.s3 import s3

LOG = logging.getLogger(__name__)

class ServiceController(wsgi.Controller):
    """The Volumes API controller for the OpenStack API."""

    def __init__(self, ext_mgr):
        self.ext_mgr = ext_mgr
        self.viewBulid = services_view.ViewBuilder()
        #self.cinder_api = volume.API()
        #self.nova_api = compute.API()
        self.server_api = server_api.ConvertAPI()
        self.swift_api = swift.API()
        super(ServiceController, self).__init__()
        
    def _check_format(self, body):
        if 'img' not in body:
            return True
        kv = ['src_img', 'des_img_name', 'destination', \
              'des_img_format', 'src_img_format']
        for k in kv:
            if k not in body['img']:
                return True
        return False

    def _check_src_img(self, context, body):
        pieces = urlparse.urlparse(body['src_img'])
        if pieces.scheme == 'file':
            if pieces.path is not None and os.access(pieces.path, os.R_OK) is False:
                return 1
        elif pieces.scheme == 'swift':
            if not self.swift_api.head_object(context, pieces.netloc, pieces.path):
                return 2
        elif pieces.scheme == 's3':
            container, _, obj_id = pieces.path.strip('/').partition('/')
            authen = pieces.netloc.split('@')
            if len(authen) < 2:
                return 2
            user = authen[0].split(':')
            if len(user) < 2:
                return 2
            s3_api = s3.API(user[0], user[1], secure=False, region=authen[1])
            try:
                s3_api.get_object(container, obj_id)
            except Exception:
                return 2
        return 0

    def _check_destination(self, context, body):
        des = []
        for d in body['destination']:
            tmp = {}
            pieces = urlparse.urlparse(d)
            if pieces.scheme == 'registry':
                tmp['name'] = 'registry'
                tmp['netloc'] = pieces.netloc
                tmp['path'] = pieces.path.strip('/')
                des.append(tmp)
            elif pieces.scheme == 'swift':
                tmp['name'] = 'swift'
                tmp['netloc'] = pieces.netloc
                tmp['path'] = pieces.path.strip('/')
                if not self.swift_api.create_container_if_missing(context, pieces.netloc, pieces.path):
                    return '1'
                des.append(tmp)
            elif pieces.scheme == 's3':
                container, _, _ = pieces.path.strip('/').partition('/')
                authen = pieces.netloc.split('@')
                if len(authen) < 2:
                    return '1'
                user = authen[0].split(':')
                if len(user) < 2:
                    return '1'
                s3_api = s3.API(user[0], user[1], secure=False, region=authen[1])
                try:
                    s3_api.get_container(container)
                except Exception:
                    return '1'
                tmp['name'] = 's3'
                tmp['netloc'] = pieces.netloc
                tmp['path'] = pieces.path.strip('/')
                des.append(tmp)
            else:
                return "unsupported destination type"
        return des

    #@wsgi.action('img_convert')
    def img_convert(self, req, body):
        """convert image api."""
        #image = body['img']
        
        context = req.environ['transformers.context']
        if self._check_format(body):
            return {'img': 'format error'}
        
        img_src = self._check_src_img(context, body['img'])
        if img_src == 1:
            return {'img': 'File does not exist or user does not \
                    have read privileges to it'}
        elif img_src == 2:
            return {'img': 'the auth user/tenant/pass is wrong or \
                    the swift/s3 object does not exist'}
        
        des = self._check_destination(context, body['img'])
        if '1' != des:
            body['img']['destination'] = des

        LOG.error('pass check')
        return {'job_id': self.server_api.img_convert(context, body)}
    
    #@wsgi.action('get_job_status')
    def get_job_status(self, req, body):
        """Returns a detailed list of resource."""
        LOG.debug("get_job_status is start.")
        context = req.environ['transformers.context']
        return {'status': self.server_api.get_job_status(context, body['id'])}

    def detail(self, req):
        """Returns a detailed list of resource."""
        LOG.debug("Detail is start.")
        context = req.environ['transformers.context']
        return self.server_api.get_all(context)    

def create_resource(ext_mgr):
    return wsgi.Resource(ServiceController(ext_mgr))
