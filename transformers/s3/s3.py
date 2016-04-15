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
from functools import wraps
import time
import random
import ssl

from libcloud.storage.drivers.s3 import S3StorageDriver
from libcloud.storage.drivers.s3 import S3Connection
from libcloud.storage.drivers.s3 import S3USWestConnection
from libcloud.storage.drivers.s3 import S3USWestOregonConnection
from libcloud.storage.drivers.s3 import S3EUWestConnection
from libcloud.storage.drivers.s3 import S3APNEConnection
from libcloud.storage.drivers.s3 import S3APSEConnection

from oslo_config import cfg

CONF = cfg.CONF


MAX_RETRY_COUNT=8

class AwsRegion:
    US_EAST_1 = 'us-east-1'
    US_WEST_1 = 'us-west-1'
    US_WEST_2 = 'us-west-2'
    EU_WEST_1 = 'eu-west-1'
    AP_NORTHEAST_1 = 'ap-northeast-1'
    AP_SOUTHEAST_1='ap-southeast-1'

DRIVER_INFO={
             AwsRegion.US_EAST_1:{'connectionCls': S3Connection,'name':'Amazon S3 (standard)','ex_location_name':''},
             AwsRegion.US_WEST_1:{'connectionCls': S3USWestConnection,'name':'Amazon S3 (us-west-1)','ex_location_name':'us-west-1'},
             AwsRegion.US_WEST_2:{'connectionCls': S3USWestOregonConnection,'name':'Amazon S3 (us-west-2)','ex_location_name':'us-west-2'},
             AwsRegion.EU_WEST_1:{'connectionCls': S3EUWestConnection,'name':'Amazon S3 (eu-west-1)','ex_location_name':'EU'},
             AwsRegion.AP_NORTHEAST_1:{'connectionCls': S3APNEConnection,'name':'Amazon S3 (ap-northeast-1)','ex_location_name':'ap-northeast-1'},
             AwsRegion.AP_SOUTHEAST_1:{'connectionCls': S3APSEConnection,'name':'Amazon S3 (ap-southeast-1)','ex_location_name':'ap-southeast-1'}
             }

class RetryDecorator(object):
    """Decorator for retrying a function upon suggested exceptions.

    The decorated function is retried for the given number of times, and the
    sleep time between the retries is incremented until max sleep time is
    reached. If the max retry count is set to -1, then the decorated function
    is invoked indefinitely until an exception is thrown, and the caught
    exception is not in the list of suggested exceptions.
    """

    def __init__(self, max_retry_count=-1, inc_sleep_time=5,
                 max_sleep_time=60, exceptions=()):
        """Configure the retry object using the input params.

        :param max_retry_count: maximum number of times the given function must
                                be retried when one of the input 'exceptions'
                                is caught. When set to -1, it will be retried
                                indefinitely until an exception is thrown
                                and the caught exception is not in param
                                exceptions.
        :param inc_sleep_time: incremental time in seconds for sleep time
                               between retries
        :param max_sleep_time: max sleep time in seconds beyond which the sleep
                               time will not be incremented using param
                               inc_sleep_time. On reaching this threshold,
                               max_sleep_time will be used as the sleep time.
        :param exceptions: suggested exceptions for which the function must be
                           retried
        """
        self._max_retry_count = max_retry_count
        self._inc_sleep_time = inc_sleep_time
        self._max_sleep_time = max_sleep_time
        self._exceptions = exceptions
        self._retry_count = 0
        self._sleep_time = 0

    def __call__(self, f):
            @wraps(f)
            def f_retry(*args, **kwargs):
                mtries, mdelay = self._max_retry_count, self._inc_sleep_time
                while mtries > 1:
                    try:
                        return f(*args, **kwargs)
                    except self._exceptions as e:
                        error_info='Second simultaneous read on fileno'
                        error_message= e.message
                        retry_error_message=['','Tunnel connection failed: 503 Service Unavailable','timed out',
                                             'Tunnel connection failed: 502 Bad Gateway',"'NoneType' object has no attribute 'makefile'"]
                        if error_message is None:
                            raise e
                        if  error_message not in retry_error_message and  not (error_info in error_message):
                            raise e
                        time.sleep(mdelay)
                        mtries -= 1
                        mdelay =random.randint(3,10)
                        if mdelay >= self._max_sleep_time:
                            mdelay=self._max_sleep_time
                return f(*args, **kwargs)
    
            return f_retry  # true decorator

class API(S3StorageDriver): 
    """
    s3Adapter
    """
    def __init__(self, key, secret=None, secure=True, host=None, port=None,
                 api_version=None, region=None, token=None,connectionCls=S3Connection, **kwargs):
        self.connectionCls,self.name,self.ex_location_name=self._get_driver_info(region)
        super(API, self).__init__(key, secret=secret, secure=secure,
                                        host=host, port=port,
                                        api_version=api_version, region=region,
                                        token=token, **kwargs)
        
        
    def _get_driver_info(self,region):
        if region is not None:
            driver_info=DRIVER_INFO.get(region,None)
            if driver_info is not None:
                return driver_info.get('connectionCls',S3Connection),driver_info.get('name','Amazon S3 (standard)'),driver_info.get('ex_location_name','')
            else:
                return S3Connection ,'Amazon S3 (standard)',''
                
                
    
    def upload_object(self, file_path, container, object_name, extra=None,
                      verify_hash=True, ex_storage_class=None):
        import boto
        s3 = boto.connect_s3(self.key, self.secret)

        bucket_name = container.name
        bucket = s3.get_bucket(bucket_name)

        from boto.s3.key import Key
        k = Key(bucket)
        k.key = object_name
        k.set_contents_from_filename(file_path)

        return self.get_object(bucket_name,object_name)

    def upload_object_via_stream(self, iterator, container, object_name,
                                 extra=None, ex_storage_class=None):
        import boto
        s3 = boto.connect_s3(self.key, self.secret)

        bucket_name = container.name
        bucket = s3.get_bucket(bucket_name)

        from boto.s3.key import Key
        k = Key(bucket)
        k.key = object_name
        k.set_contents_from_file(iterator)

        return self.get_object(bucket_name,object_name)

    def download_object(self, obj, destination_path, overwrite_existing=False,
                    delete_on_failure=True):
        import boto
        from boto.s3.key import Key

        s3 = boto.connect_s3(self.key, self.secret)

        bucket_name = obj.container.name
        object_name = obj.name

        bucket = s3.get_bucket(bucket_name)
        k = Key(bucket)
        k.key = object_name
        k.get_contents_to_filename(destination_path)
        
        
#     @RetryDecorator(max_retry_count= MAX_RETRY_COUNT,inc_sleep_time=5,max_sleep_time=60,
#                         exceptions=(Exception,ssl.SSLError)) 
    def get_object(self, container_name, object_name):
        return super(API, self).get_object(container_name, object_name)
    
    @RetryDecorator(max_retry_count= MAX_RETRY_COUNT,inc_sleep_time=5,max_sleep_time=60,
                        exceptions=(Exception,ssl.SSLError)) 
    def delete_object(self, obj):
        return super(API, self).delete_object(obj)
    
    @RetryDecorator(max_retry_count= MAX_RETRY_COUNT,inc_sleep_time=5,max_sleep_time=60,
                        exceptions=(Exception,ssl.SSLError)) 
    def create_container(self, container_name):
        return super(API, self).create_container(container_name)
    
    @RetryDecorator(max_retry_count= MAX_RETRY_COUNT,inc_sleep_time=5,max_sleep_time=60,
                        exceptions=(Exception,ssl.SSLError)) 
    def get_container(self, container_name):
        return super(API,self).get_container(container_name)