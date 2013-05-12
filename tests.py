# -*- coding: utf-8 -*-
from flask import Flask
from flask.ext.testing import TestCase
from flask_slither import register_api, BaseAPI
from pymongo import MongoClient

""" Vanilla extention of BaseAPI so we can test all BaseAPI functionality
as-is"""

collection_name = 'tests'


class TestApi(BaseAPI):
    collection = collection_name


class BaseApiTestCase(TestCase):
    def create_app(self):
        app = Flask(__name__)

        app.config['DB_HOST'] = 'localhost'
        app.config['DB_PORT'] = 27017
        app.config['DB_NAME'] = 'test_slither'
        app.client = MongoClient(app.config['DB_HOST'], app.config['DB_PORT'])
        app.db = app.client[app.config['DB_NAME']]

        # register route endpoints of BaseApi for testing
        register_api(app, TestApi, url="test")
        return app

    def setUp(self):
        self._fixture_setup()

    def tearDown(self):
        self.app.db[collection_name].drop()

    def test_get_list(self):
        response = self.client.get('/test')
        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.json.keys(), [collection_name])
        self.assertEquals(len(response.json[collection_name]), 10)
        for i in range(10):
            self.assertEquals(response.json[collection_name][i]['name'],
                              "Record %s" % i)

    def test_get_instance_by_id(self):
        obj_id = self.app.db[collection_name].find_one()['_id']
        response = self.client.get('/test/%s' % str(obj_id))
        self.assertEquals(response.status_code, 200)
        expected_data = {collection_name: {
            '_id': {"$oid": str(obj_id)}, 'name': "Record 0"}}
        self.assertEquals(response.json, expected_data)

    def test_get_instance_by_lookup(self):
        obj_id = self.app.db[collection_name].find_one()['_id']
        response = self.client.get('/test/Record 0')
        self.assertEquals(response.status_code, 200)
        expected_data = {collection_name: {
            '_id': {"$oid": str(obj_id)}, 'name': "Record 0"}}
        self.assertEquals(response.json, expected_data)

    def _fixture_setup(self):
        for i in range(10):
            self.app.db[collection_name].insert(
                {'name': "Record %s" % i})
