# -*- coding: utf-8 -*-
from flask import current_app, request


class NoAuthorization():
    """ The default authorization always returns true. All requests are
    authorized"""
    def is_authorized(self, **kwargs):
        current_app.logger.warning(
            "Authorization:API is open - no authorization checks in place")
        return True


class ReadOnlyAuthorization():
    """ Only GET requests are allowed, the rests are disallowed"""
    def is_authorized(self, **kwargs):
        current_app.logger.info("Authorization: API is read-only")
        return request.method == "GET"
