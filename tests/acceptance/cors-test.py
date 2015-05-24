# -*- coding: utf-8 -*-
# The cors test ensures that the CORS functionality is working for resources.

from bson.objectid import ObjectId
from flask import Flask
from flask_slither import register_resource
from flask_slither.resources import BaseResource
from pymongo import MongoClient

import json
import unittest


class CorsResource(BaseResource):
    db_collection = 'cors'
    cors_enabled = True


class CorsTest(unittest.TestCase):

    def setUp(self):
        self.app = Flask('Cors')
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        register_resource(self.app, CorsResource, url="cors")

        self.db_client = MongoClient('localhost', 27017)
        self.db = self.db_client['test_slither']
        self._load_fixtures()

    def tearDown(self):
        self.db['cors'].drop()
        self.db_client.close()
        self.client = None
        self.app = None

    def _load_fixtures(self):
        fixtures = [
            {'name': "Cors single record"},
        ]
        for f in fixtures:
            self.db['cors'].insert(f)

    def test_basic_check(self):
        """Check header of get response to ensure it matches CORS spec"""
        with self.app.test_client() as c:
            r = c.open('/cors', method='OPTIONS')
            self.assertEquals(r.status_code, 200)
            expected_headers = {
                #  'access-control-allow-origin': "http://localhost",
                'access-control-allow-methods':
                "GET, POST, PUT, PATCH, DELETE, OPTIONS",
                'access-control-max-age': "21600",
            }
            for k, v in expected_headers.items():
                self.assertEquals(
                    r.headers.get(k), v, "Bad header: {}".format(k))
            self.assertFalse('access-control-allow-headers' in r.headers)

    def test_check_rq_header(self):
        """Check header of get response to ensure it matches CORS spec"""
        with self.app.test_client() as c:
            headers = {'access-control-request-headers': "Authorization"}
            r = c.open('/cors', method='OPTIONS',
                       headers=headers)
            self.assertEquals(r.status_code, 200)
            self.assertEquals(r.headers['access-control-allow-headers'],
                              'Authorization')
