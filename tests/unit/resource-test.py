# -*- coding: utf-8 -*-
# Tests the various class variables on a resource to ensure they behave as
# expected

from flask import Flask, g
from flask_slither import register_resource
from flask_slither.resources import BaseResource
import unittest


class TypeTest(unittest.TestCase):
    """Ensure only the allowed types return valid responses"""

    def setUp(self):
        self.app = Flask('Types')
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        BaseResource.db_collection = 'Bogus'

    def _register(self, method):
        BaseResource.allowed_methods = [method.upper()]
        register_resource(self.app, BaseResource, url="types")

    def test_get(self):
        self._register('get')
        r = self.client.get('/types')
        self.assertEquals(r.status_code, 200, "Method GET allowed")

        for m in ['post', 'patch', 'put', 'delete']:
            r = getattr(self.client, m)('/types')
            self.assertEquals(r.status_code, 405,
                              "Method {} not allowed".format(m.upper()))

    def test_post(self):
        self._register('post')
        r = self.client.post('/types')
        self.assertEquals(r.status_code, 201, "Method POST allowed")

        for m in ['get', 'patch', 'put', 'delete']:
            r = getattr(self.client, m)('/types')
            self.assertEquals(r.status_code, 405,
                              "Method {} not allowed".format(m.upper()))

    def test_put(self):
        self._register('put')
        r = self.client.put('/types/1')
        self.assertEquals(r.status_code, 204, "Method PUT allowed")

        for m in ['get', 'post', 'patch', 'delete']:
            r = getattr(self.client, m)('/types')
            self.assertEquals(r.status_code, 405,
                              "Method {} not allowed".format(m.upper()))

    def test_patch(self):
        self._register('patch')
        r = self.client.patch('/types/1')
        self.assertEquals(r.status_code, 204, "Method PATCH allowed")

        for m in ['get', 'post', 'put', 'delete']:
            r = getattr(self.client, m)('/types')
            self.assertEquals(r.status_code, 405,
                              "Method {} not allowed".format(m.upper()))

    def test_delete(self):
        self._register('delete')
        r = self.client.delete('/types/1')
        self.assertEquals(r.status_code, 204, "Method DELETE allowed")

        for m in ['get', 'post', 'put', 'patch']:
            r = getattr(self.client, m)('/types')
            self.assertEquals(r.status_code, 405,
                              "Method {} not allowed".format(m.upper()))


class AuthenticationTest(unittest.TestCase):
    """Ensure authentication method is run"""

    def setUp(self):
        self.app = Flask('Authentication')
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        BaseResource.db_collection = 'None'

    def test_undefined(self):
        """No authentication method is defined"""
        delattr(BaseResource, 'authentication')
        register_resource(self.app, BaseResource, url="authentications")
        r = self.client.get('/authentications')
        self.assertEquals(r.status_code, 200, "No authentication")

    def test_none(self):
        """The authentication method is set to None"""
        BaseResource.authentication = None
        register_resource(self.app, BaseResource, url="authentications")
        r = self.client.get('/authentications')
        self.assertEquals(r.status_code, 200, "No authentication")

    def test_empty(self):
        """The authentication is_authenticated method does not exist"""

        class MyAuth:
            pass

        BaseResource.authentication = MyAuth
        register_resource(self.app, BaseResource, url="authentications")
        r = self.client.get('/authentications')
        self.assertEquals(r.status_code, 200, "No authentication")

    def test_success(self):
        """The authentication method returns True"""

        class MyAuth:
            def is_authenticated(self):
                return True

        BaseResource.authentication = MyAuth
        register_resource(self.app, BaseResource, url="authentications")
        r = self.client.get('/authentications')
        self.assertEquals(r.status_code, 200, "Successful Authentication")

    def test_fail(self):
        """The authentication method returns False"""

        class MyAuth:
            def is_authenticated(self):
                return False

        BaseResource.authentication = MyAuth
        register_resource(self.app, BaseResource, url="authentications")
        r = self.client.get('/authentications')
        self.assertEquals(r.status_code, 401, "Unsuccessful Authentication")


class AuthorizationTest(unittest.TestCase):
    """Ensure authorization method is run"""

    def setUp(self):
        self.app = Flask('authorization')
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        BaseResource.db_collection = 'None'

    def test_undefined(self):
        """No authorization method is definedtest_"""
        delattr(BaseResource, 'authentication')
        register_resource(self.app, BaseResource, url="authorizations")
        r = self.client.get('/authorizations')
        self.assertEquals(r.status_code, 200, "No authorization")

    def test_none(self):
        """The authorization method is set to None"""
        BaseResource.authentication = None
        register_resource(self.app, BaseResource, url="authorizations")
        r = self.client.get('/authorizations')
        self.assertEquals(r.status_code, 200, "No authorization")

    def test_empty(self):
        """The authorization is_authorized method does not exist"""

        class MyAuth:
            pass

        BaseResource.authentication = MyAuth
        register_resource(self.app, BaseResource, url="authorizations")
        r = self.client.get('/authorizations')
        self.assertEquals(r.status_code, 200, "No authorization")

    def test_success(self):
        """The authorization method returns True"""

        class MyAuth:
            def is_authorized(self, **kwargs):
                return True

        BaseResource.authentication = MyAuth
        register_resource(self.app, BaseResource, url="authorizations")
        r = self.client.get('/authorizations')
        self.assertEquals(r.status_code, 200, "Successful authorization")

    def test_fail(self):
        """The authorization method returns False"""

        class MyAuth:
            def is_authorized(self, **kwargs):
                return False

        BaseResource.authentication = MyAuth
        register_resource(self.app, BaseResource, url="authorizations")
        r = self.client.get('/authorizations')
        self.assertEquals(r.status_code, 403, "Unsuccessful authorization")

    def test_record_ref(self):
        """The authorization method returns True if the url record is found"""

        class MyAuth:
            def is_authorized(self, **kwargs):
                return hasattr(g, '_resource_instance')

        BaseResource.authentication = MyAuth
        register_resource(self.app, BaseResource, url="authorizations")
        r = self.client.delete('/authorizations/1')
        self.assertEquals(r.status_code, 204, "Successful authorization")
