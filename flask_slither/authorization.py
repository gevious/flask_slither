from flask import current_app, request


class NoAuthorization():
    """ The default authorization always returns true. All requests are
    authorized"""
    def is_authorized(self, **kwargs):
        current_app.logger.warning(
            "Authorization:API is open - no auth checks in place")
        return True

    def access_limits(self, **kwargs):
        current_app.logger.warning(
            "Access Limits: No query access restrictions")
        return None


class ReadOnlyAuthorization():
    """ Only GET requests are allowed, the rests are disallowed"""
    def is_authorized(self, **kwargs):
        current_app.logger.info("Authorization: API is read-only")
        return request.method == "GET"

    def access_limits(self, **kwargs):
        current_app.logger.warning(
            "Access Limits: No query access restrictions")
        return None
