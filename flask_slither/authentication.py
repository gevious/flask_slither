from dateutil import parser
from datetime import datetime, timedelta
from flask import current_app, request, g
from flask.ext.slither.signals import request_authenticated
from hashlib import sha1

import binascii
import hmac
import pytz


class NoAuthentication():
    """ The default authentication allows all requests through """
    def is_authenticated(self, **kwargs):
        current_app.logger.info("Authentication: No Auth checks in place")
        return True


class RequestSigningAuthentication():
    """This authentication method is based on amazon's request signing. It
    has a few tweaks that might be needed for most applications:
     * A `fs-site` header is needed for routing a request to a certain site.
       This can just be a custom value, but for multi tenent approach, it is
       useful to have a site differentiator built into authentication
     * A `fs-date` header which contains the current date
     * The `authorization` header is built up from the current request. It is
       in the format 'FS access_key:signature'

    If the request is successful, the authenticated user is stored in the
    global object for later use.

    Note: For this to work the site must have a sites collection with
    records having a name and a key field. The key is passed in the header.
    Also, the users collection must exist with a username field as well as a
    subdoc consisting of access_key, secret_key"""

    def is_authenticated(self, **kwargs):
        if request.method == 'OPTIONS':
            current_app.logger.info("Allowing OPTIONS request through")
            return True

        if current_app.config.get('DEBUG', False) is True:
            current_app.logger.warning("In DEBUG mode. No Auth Required")
            g.site = current_app.db['sites'].find_one()
            if g.site is None:
                g.authentication_error = "No site in database"
                return False
            g.user = current_app.db['users'].find_one(
                {'site': g.site['_id'], 'is_superuser': True})
            if g.user is None:
                g.authentication_error = "No superuser in database"
                return False
            current_app.logger.info("Logged in as %s on %s" %
                                    (g.user['username'], g.site['name']))
            request_authenticated.send(current_app._get_current_object(),
                                       user=g.user)
            return True

        if 'Fs-Site' not in request.headers:
            g.authentication_error = "No site specified"
            return False
        g.site = current_app.db['sites'].find_one(
            {'key': request.headers['Fs-Site']})
        if g.site is None:
            g.authentication_error = "Invalid site"
            return False

        if 'Authorization' not in request.headers:
            g.authentication_error = "No authorization header"
            return False

        current_app.logger.debug(
            "Authorization Header: %s" % request.headers['Authorization'])
        if request.headers['Authorization'].find('FS ') != 0:
            current_app.logger.debug("Missing FS prefix in auth header")
            g.authentication_error = "Malformed authorization header"
            return False

        date = request.headers.get('Fs-Date', None)
        if date is None:
            current_app.logger.debug("Missing FS-Date or date from header")
            g.authentication_error = "Missing date in header"
            return False

        # check date is not older than 15 minutes
        date = parser.parse(date)
        now = datetime.now(pytz.timezone(current_app.config['TIMEZONE']))
        current_app.logger.debug("Current Date: %s" % now)
        current_app.logger.debug("Request Date: %s" % date)
        if date + timedelta(minutes=15) < now or \
                date - timedelta(minutes=15) > now:
            current_app.logger.warning("Request outside 15 minute window")
            g.authentication_error = "Date is outside auth window period"
            return False
        signature = request.headers['Authorization'][3:].split(':')
        access_key = signature[0]
        signature = signature[1]

        g.user = current_app.db['users'].find_one(
            {'site': g.site['_id'], 'auth.access_key': access_key})
        if g.user is None:
            current_app.logger.debug("No matching access key found")
            g.authentication_error = "Access denied"
            return False
        secret_key = str(g.user['auth']['secret_key'])

        h = request.host if request.host.find('.') < 0 \
            else request.host.split('.')[0]
        resource = "/%s%s" % (h, request.environ['PATH_INFO'])
        content_type = request.headers.get('content-type', "").lower()

        # Added this to match header for multipart-form uploads in unit tests
        if ';' in content_type:
            content_type = content_type.split(';')[0]

        string_to_sign = (
            u"%(verb)s\n%(type)s\n%(content-md5)s\n"
            u"%(date)s\n%(resource)s") % {
                'verb': request.method.lower(),
                'type': content_type,
                'content-md5': request.headers.get('content-md5', "").lower(),
                'date': request.headers.get('fs-date').lower(),
                'resource': resource}
        current_app.logger.debug("String to sign: %s" % string_to_sign)
        hashed = hmac.new(secret_key, string_to_sign, sha1)
        calculated_signature = binascii.b2a_base64(hashed.digest())[:-1]
        current_app.logger.debug("Signature: %s" % calculated_signature)
        # Return true if sent signature == calculated signature
        if signature != calculated_signature:
            g.authentication_error = "Invalid Signature"
            return False
        request_authenticated.send(current_app._get_current_object(),
                                   user=g.user)

        current_app.logger.info("Authentication: No Auth checks in place")
        return True
