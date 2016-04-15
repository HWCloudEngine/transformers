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

"""Cinder base exception handling.

Includes decorator for re-raising Cinder-type exceptions.

SHOULD include dedicated exception logging.

"""

import sys

from oslo_config import cfg
import six
import webob.exc

from transformers.common import log as logging

from transformers.i18n import _, _LE


LOG = logging.getLogger(__name__)

exc_log_opts = [
    cfg.BoolOpt('fatal_exception_format_errors',
                default=False,
                help='Make exception message format errors fatal.'),
]

CONF = cfg.CONF
CONF.register_opts(exc_log_opts)


class ConvertedException(webob.exc.WSGIHTTPException):
    def __init__(self, code=400, title="", explanation=""):
        self.code = code
        self.title = title
        self.explanation = explanation
        super(ConvertedException, self).__init__()


class Error(Exception):
    pass


class TransException(Exception):
    """Base Cinder Exception

    To correctly use this class, inherit from it and define
    a 'message' property. That message will get printf'd
    with the keyword arguments provided to the constructor.

    """
    message = _("An unknown exception occurred.")
    code = 500
    headers = {}
    safe = False

    def __init__(self, message=None, **kwargs):
        self.kwargs = kwargs
        self.kwargs['message'] = message

        if 'code' not in self.kwargs:
            try:
                self.kwargs['code'] = self.code
            except AttributeError:
                pass

        for k, v in self.kwargs.iteritems():
            if isinstance(v, Exception):
                self.kwargs[k] = six.text_type(v)

        if self._should_format():
            try:
                message = self.message % kwargs

            except Exception:
                exc_info = sys.exc_info()
                # kwargs doesn't match a variable in the message
                # log the issue and the kwargs
                LOG.exception(_LE('Exception in string format operation'))
                for name, value in kwargs.iteritems():
                    LOG.error(_LE("%(name)s: %(value)s"),
                              {'name': name, 'value': value})
                if CONF.fatal_exception_format_errors:
                    raise exc_info[0], exc_info[1], exc_info[2]
                # at least get the core message out if something happened
                message = self.message
        elif isinstance(message, Exception):
            message = six.text_type(message)

        # NOTE(luisg): We put the actual message in 'msg' so that we can access
        # it, because if we try to access the message via 'message' it will be
        # overshadowed by the class' message attribute
        self.msg = message
        super(TransException, self).__init__(message)

    def _should_format(self):
        return self.kwargs['message'] is None or '%(message)' in self.message

    def __unicode__(self):
        return six.text_type(self.msg)



class NotAuthorized(TransException):
    message = _("Not authorized.")
    code = 403


class AdminRequired(NotAuthorized):
    message = _("User does not have admin privileges")


class Invalid(TransException):
    message = _("Unacceptable parameters.")
    code = 400


class SfJsonEncodeFailure(TransException):
    message = _("Failed to load data into json format")


class InvalidResults(Invalid):
    message = _("The results are invalid.")


class InvalidInput(Invalid):
    message = _("Invalid input received: %(reason)s")


class InvalidContentType(Invalid):
    message = _("Invalid content type %(content_type)s.")


# Cannot be templated as the error syntax varies.
# msg needs to be constructed when raised.
class InvalidParameterValue(Invalid):
    message = _("%(err)s")


class InvalidAuthKey(Invalid):
    message = _("Invalid auth key: %(reason)s")


class InvalidConfigurationValue(Invalid):
    message = _('Value "%(value)s" is not valid for '
                'configuration option "%(option)s"')


class ServiceUnavailable(Invalid):
    message = _("Service is unavailable at this time.")


class InvalidUUID(Invalid):
    message = _("Expected a uuid but received %(uuid)s.")


class APIException(TransException):
    message = _("Error while requesting %(service)s API.")

    def __init__(self, message=None, **kwargs):
        if 'service' not in kwargs:
            kwargs['service'] = 'unknown'
        super(APIException, self).__init__(message, **kwargs)


class APITimeout(APIException):
    message = _("Timeout while requesting %(service)s API.")


class NotFound(TransException):
    message = _("Resource could not be found.")
    code = 404
    safe = True

class FileNotFound(NotFound):
    message = _("File %(file_path)s could not be found.")


class MalformedRequestBody(TransException):
    message = _("Malformed message body: %(reason)s")


class ConfigNotFound(NotFound):
    message = _("Could not find config at %(path)s")


class ParameterNotFound(NotFound):
    message = _("Could not find parameter %(param)s")


class PasteAppNotFound(NotFound):
    message = _("Could not load paste app '%(name)s' from %(path)s")


class NoValidHost(TransException):
    message = _("No valid host was found. %(reason)s")


class NoMoreTargets(TransException):
    """No more available targets."""
    pass


class QuotaError(TransException):
    message = _("Quota exceeded: code=%(code)s")
    code = 413
    headers = {'Retry-After': 0}
    safe = True

class EvaluatorParseException(Exception):
    message = _("Error during evaluator parsing: %(reason)s")


class ObjectActionError(TransException):
    msg_fmt = _('Object action %(action)s failed because: %(reason)s')


class ObjectFieldInvalid(TransException):
    msg_fmt = _('Field %(field)s of %(objname)s is not an instance of Field')


class UnsupportedObjectError(TransException):
    msg_fmt = _('Unsupported object type %(objtype)s')


class OrphanedObjectError(TransException):
    msg_fmt = _('Cannot call %(method)s on orphaned %(objtype)s object')


class IncompatibleObjectVersion(TransException):
    msg_fmt = _('Version %(objver)s of %(objname)s is not supported')


# ZFSSA NFS driver exception.
class WebDAVClientError(TransException):
        message = _("The WebDAV request failed. Reason: %(msg)s, "
                    "Return code/reason: %(code)s, Source Volume: %(src)s, "
                    "Destination Volume: %(dst)s, Method: %(method)s.")


class Forbidden(TransException):
    ec2_code = 'AuthFailure'
    msg_fmt = _("Not authorized.")
    code = 403

class ReadOnlyFieldError(TransException):
    msg_fmt = _('Cannot modify readonly field %(field)s')

class ExcuteImage2dockerError(TransException):
    message = _('execute image2docker fails')