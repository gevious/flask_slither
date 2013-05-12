from flask import current_app


class NoAuthentication():
    """ The default authentication allows all requests through """
    def is_authenticated(self, **kwargs):
        current_app.logger.info("Authentication: No Auth checks in place")
        return True
