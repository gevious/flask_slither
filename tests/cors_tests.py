# -*- coding: utf-8 -*-
from flask import Flask
from flask.ext.testing import TestCase
from flask.ext.slither.resources import BaseResource
from flask.ext.slither import register_api
from pymongo import MongoClient
from tests.default_tests import RegexConverter
from unittest import skip


collection_name = 'tests'


class CorsResource(BaseResource):
    collection = collection_name
    cors_enabled = True


class CORS(TestCase):
    """ Test CORS functionality both for allowed and disallowed cross-origin
    requests"""

    def create_app(self):
        app = Flask(__name__)
        app.url_map.converters['regex'] = RegexConverter

        app.config['DB_HOST'] = 'localhost'
        app.config['DB_PORT'] = 27017
        app.config['DB_NAME'] = 'test_slither'
        app.client = MongoClient(app.config['DB_HOST'], app.config['DB_PORT'])
        app.db = app.client[app.config['DB_NAME']]

        # url includes a company part which should be an id
        url = '<regex("[a-f0-9]{24}"):company>/test'
        register_api(app, CorsResource, url=url)
        return app

    def setUp(self):
        # Insert test records
        for i in range(10):
            self.app.db[collection_name].insert(
                {'name': "Record %s" % i, 'extra': "Extra %s" % i})
        self.app.db['users'].insert(
            {'username': "testuser", 'auth': {
                'access_key': "super", 'secret_key': "duper"}})
        u_id = str(self.app.db['users'].find_one()['_id'])
        self.url = "/%s/test" % u_id

    def tearDown(self):
        self.app.db[collection_name].drop()
        self.app.db['users'].drop()

    def test_basic_check(self):
        """Check header of get response to ensure it matches CORS spec"""
        with self.app.test_client() as c:
            r = c.open(self.url, method='OPTIONS')
            self.assertEquals(r.status_code, 200)
            expected_headers = {
                'access-control-allow-origin': "http://localhost",
                'access-control-allow-methods':
                "GET, POST, PUT, PATCH, DELETE, OPTIONS",
                'access-control-max-age': "21600",
            }
            for k, v in expected_headers.iteritems():
                self.assertEquals(r.headers.get(k), v, "Bad header: %s" % k)
            self.assertFalse('access-control-allow-headers' in r.headers)

    def test_check_rq_header(self):
        """Check header of get response to ensure it matches CORS spec"""
        with self.app.test_client() as c:
            headers = {'access-control-request-headers': "Authorization"}
            r = c.open(self.url, method='OPTIONS',
                       headers=headers)
            self.assertEquals(r.status_code, 200)
            self.assertEquals(r.headers['access-control-allow-headers'],
                              'Authorization')

    @skip("Test blacklisted origin")
    def test_blacklisted(self):
        pass

    @skip("Test Included origins")
    def test_included(self):
        pass
