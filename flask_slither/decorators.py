# -*- coding: utf-8 -*-
from flask import make_response, request, current_app, Response, g, json
from functools import wraps
from urllib.parse import urlparse


def crossdomain(f):
    """This decorator sets the rules for the crossdomain request per http
       method. The settings are taken from the actual resource itself, and
       returned as per the CORS spec.

       All CORS requests are rejected if the resource's `allow_methods`
       doesn't include the 'OPTIONS' method. """
    @wraps(f)
    def decorator(self, *args, **kwargs):
        # TODO: if a non-cors request has the origin header, this will fail
        if not self.cors_enabled and 'origin' in request.headers:
            return self._make_response(405, "CORS request rejected")
        resp = f(self, *args, **kwargs)

        h = resp.headers
        current_app.logger.debug("Request Headers: {}".format(request.headers))
        allowed_methods = self.cors_config['methods'] + ["OPTIONS"]
        h['Access-Control-Allow-Methods'] = ", ".join(allowed_methods)
        h['Access-Control-Max-Age'] = self.cors_config.get('max_age', 21600)

        # Request Origin checks
        hostname = urlparse(request.headers['origin']).netloc \
            if 'origin' in request.headers else request.headers['host']
        if hostname in self.cors_config.get('blacklist', []):
            return self._make_response(405, "CORS request blacklisted")
        if self.cors_config.get('allowed', None) is not None and \
                hostname not in self.cors_config.get('allowed', None):
            return self._make_response(405, "CORS request refused")
        if 'origin' in request.headers:
            h['Access-Control-Allow-Origin'] = request.headers['origin']

        # Request header checks
        if 'access-control-request-headers' in request.headers:
            if self.cors_config.get('headers', None) is None:
                allowed_headers = \
                    request.headers.get('access-control-request-headers', "*")
            else:
                allowed_headers = []
                for k in request.headers.get(
                        'access-control-request-headers', []):
                    if k in self.cors_config.get('headers', []):
                        allowed_headers.append(k)
                allowed_headers = " ,".join(allowed_headers)
            h['Access-Control-Allow-Headers'] = allowed_headers

        return resp
    return decorator


def endpoint(f):
    """This decorator marks this method as an endpoint. It is responsible for
       the request workflow and will call each relevant method in turn."""

    def check_authentication(self, **kwargs):
        """If the `authentication` variable is defined and not None, the
           specified method will be run. On True the request will continue
           otherwise it will fail with a 401 authentication error"""
        if getattr(self, 'authentication', None) is None:
            current_app.logger.debug("No authentication method")
            return

        a = self.authentication()
        if not hasattr(a, 'is_authenticated'):
            current_app.logger.debug("No is_authenticated method")
            return

        if not a.is_authenticated(**kwargs):
            current_app.logger.warning("Authentication failed")
            return self._make_response(401, "Authentication failed",
                                       abort=True)
        current_app.logger.debug("Authentication successful")

    def check_authorization(self):
        """If the `authorization` variable is defined and not None, the
           specified method will be run. On True the request will continue
           otherwise it will fail with a 403 authorization error"""
        current_app.logger.info("Checking authentication/authorization")
        auth_class = getattr(self, 'authorization',
                             getattr(self, 'authentication', None))
        if auth_class is None:
            current_app.logger.debug("No authorization class")
            return

        a = auth_class()
        if not hasattr(a, 'is_authorized'):
            current_app.logger.debug("No is_authorized method")
            return

        if not a.is_authorized(record=g._resource_instance):
            current_app.logger.warning("Authorization failed")
            return self._make_response(403, "Authorization failed", abort=True)
        current_app.logger.debug("Authorization successful")

    def validate_request(self, **kwargs):
        """Call the validator class and validate the request_data. This method
           returns True or False. On False, a 400 will be returned with the
           reasons for the validation error. On True, the operation will
           continue."""
        current_app.logger.info(
            "Checking {} validation".format(request.method))
        if getattr(self, 'validation', None) is None:
            current_app.logger.warning("No validation specified")
            return

        v = self.validation()
        method = 'validate_{}'.format(request.method.lower())

        if not hasattr(v, method):
            current_app.logger.warning("No validation method specified")
            return
        errors = getattr(v, method)(**kwargs)
        current_app.logger.debug("Validation errors: {}".format(errors))

        if errors is not None and len(errors) > 0:
            current_app.logger.warning("Validation errors found")
            self._make_response(400, errors, abort=True)

    def load_request_data(self):
        if request.method in ['GET', 'DELETE']:
            return
        current_app.logger.info("Saving json payload in memory")
        # For now we assume JSON. Later in life we can make this more
        # payload agnostic
        try:
            d = request.data.decode('utf-8')
            g._rq_data = {} if d.strip() == "" else json.loads(d)
        except ValueError:
            return self._make_response(400, "Malformed JSON in request body",
                                       abort=True)

        if self.enforce_json_root and g._rq_data != {} and \
                list(g._rq_data.keys()) != [self._payload_root()]:
            msg = "Invalid JSON root in request body"
            current_app.logger.error(msg)
            current_app.logger.debug(
                "Found {}, expecting {}".format(
                    list(g._rq_data.keys()), self._payload_root()))
            return self._make_response(400, msg, abort=True)
        elif self._payload_root() in list(g._rq_data.keys()):
                current_app.logger.debug("Removing JSON root from rq payload")
                g._rq_data = g._rq_data[self._payload_root()]
        current_app.logger.debug("g._rq_data: {}".format(g._rq_data))
        return g._rq_data

    @wraps(f)
    def decorator(self, *args, **kwargs):
        current_app.logger.info("Got {} request".format(request.method))
        current_app.logger.info("Endpoint: {}".format(request.url))
        if request.method not in self.allowed_methods:
            msg = "Request method {} is unavailable".format(request.method)
            current_app.logger.error(msg)
            return self._make_response(405, msg, abort=True)

        current_app.logger.info("Checking db table/collection is defined")
        if self.enforce_payload_collection and self.db_collection is None:
            msg = "No DB collection defined"
            current_app.logger.error(msg)
            return make_response(Response(msg, 424))

        if request.method in ['POST', 'PUT', 'PATCH']:
            load_request_data(self)

        check_authentication(self, **kwargs)
        if kwargs.get('obj_id', False):
            kwargs['obj_id'] = self.fiddle_id(kwargs['obj_id'])
            self._get_instance(**kwargs)
        else:
            g._resource_instance = {}

        if request.method in ['POST', 'PUT', 'PATCH']:
            check_authorization(self)
            r = self.transform_record(g._rq_data.get(self._payload_root(),
                                                     g._rq_data))
            g._saveable_record = dict(self.merge_record_data(
                r, dict(getattr(g, '_resource_instance', r))))
            validate_request(self, data=g._saveable_record)
        else:
            check_authorization(self)
            validate_request(self)
        return f(self, *args, **kwargs)
    return decorator
