from flask import current_app, request, g


class NoAuthorization():
    """ The default authorization always returns true. All requests are
    authorized"""
    def is_authorized(self, **kwargs):
        current_app.logger.warning(
            "Authorization:API is open - no authorization checks in place")
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


class SiteOnlyAuthorization():
    """ All access to records within the site"""
    def is_authorized(self, **kwargs):
        current_app.logger.info("Authorization: Only the site is visible")
        return True

    def access_limits(self, **kwargs):
        current_app.logger.warning("Access Limits: Site wide access")
        if g.user.get('is_superuser', False) or \
                g.user.get('is_site_manager', False):
            return {'site': g.site['_id']}
        has_perms = False
        perm = {'GET': "view", 'POST': "add", 'PATCH': "change",
                'DELETE': "delete"}

        for group in g.user.get('groups', []):
            if "%s_%s" % (perm[request.method], self.collection[:-1]) in \
                    group.get('permissions', []):
                has_perms = True
                break
        return has_perms
