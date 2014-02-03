# -*- coding: utf-8 -*-
from bson.objectid import ObjectId
from bson import json_util
from flask import request, current_app, g
from functools import wraps
from urlparse import urlparse


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
            return self._prep_response("CORS request rejected", status=405)
        resp = f(self, *args, **kwargs)

        h = resp.headers
        current_app.logger.debug("Request Headers: %s" % request.headers)
        allowed_methods = self.cors_methods + ["OPTIONS"]
        h['Access-Control-Allow-Methods'] = ", ".join(allowed_methods)
        h['Access-Control-Max-Age'] = str(self.cors_max_age)

        # Request Origin checks
        hostname = urlparse(request.headers['origin']).netloc \
            if 'origin' in request.headers else request.headers['host']
        if hostname in self.cors_blacklist:
            return self._prep_response("CORS request blacklisted", status=405)
        if self.cors_allowed is not None and hostname not in self.cors_allowed:
            return self._prep_response("CORS request refused", status=405)
        h['Access-Control-Allow-Origin'] = "%s://%s" % \
            (request.headers.environ['wsgi.url_scheme'], hostname)

        # Request header checks
        if 'access-control-request-headers' in request.headers:
            if self.cors_headers is None:
                allowed_headers = \
                    request.headers.get('access-control-request-headers', "*")
            else:
                allowed_headers = []
                for k in request.headers.get(
                        'access-control-request-headers', []):
                    if k in self.cors_headers:
                        allowed_headers.append(k)
                allowed_headers = " ,".join(allowed_headers)
            h['Access-Control-Allow-Headers'] = allowed_headers

        return resp
    return decorator


def preflight_checks(f):
    """ This decorator does any checks before the request is allowed through.
    This includes authentication, authorization, throttling and caching."""
    @wraps(f)
    def decorator(self, *args, **kwargs):
        if request.method not in self.allowed_methods:
            return self._prep_response("Method Unavailable", status=405)
        if self.collection is None:
            return self._prep_response("No collection defined",
                                       status=424)

        if 'obj_id' in kwargs:
            kwargs['obj_id'] = ObjectId(kwargs['obj_id'])

        current_app.logger.debug("%s request received" %
                                 request.method.upper())
        if not self.authentication.is_authenticated(**kwargs):
            msg = g.authentication_error \
                if hasattr(g, 'authentication_error') else None
            current_app.logger.warning("Unauthenticated request")
            return self._prep_response(msg, status=401)
        if not self.authorization.is_authorized(
                model=self.model, collection=self.collection, **kwargs):
            current_app.logger.warning("Unauthorized request")
            msg = g.authorization_error \
                if hasattr(g, 'authorization_error') else None
            return self._prep_response(msg, status=403)
        if request.method in ['POST', 'PUT', 'PATCH']:
            # enforcing collection as root of payload
            g.s_data = {} if request.data.strip() == "" else \
                json_util.loads(request.data)
            if self._get_root() not in g.s_data:
                if self.enforce_payload_collection:
                    return self._prep_response("No collection in payload",
                                               status=400)
            else:
                g.s_data = g.s_data[self._get_root()]

        return f(self, *args, **kwargs)
    return decorator
