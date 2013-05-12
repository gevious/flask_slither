# -*- coding: utf-8 -*-
from flask import Flask
from flask.ext.testing import TestCase
from flask.ext.slither.endpoints import BaseEndpoints
from flask.ext.slither import register_api
from pymongo import MongoClient
from unittest import skip

""" Vanilla extention of BaseAPI so we can test all BaseAPI functionality
as-is"""

collection_name = 'tests'


class TestEndpoints(BaseEndpoints):
    collection = collection_name


class BaseEndpointsTestCase(TestCase):
    def create_app(self):
        app = Flask(__name__)

        app.config['DB_HOST'] = 'localhost'
        app.config['DB_PORT'] = 27017
        app.config['DB_NAME'] = 'test_slither'
        app.client = MongoClient(app.config['DB_HOST'], app.config['DB_PORT'])
        app.db = app.client[app.config['DB_NAME']]

        # register route endpoints of BaseApi for testing
        register_api(app, TestEndpoints, url="test")
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

    @skip("Get list with limited fields")
    def test_get_list_limit_fields(self):
        #Limit fields returned by instance
        pass

    def test_get_instance_by_id(self):
        obj_id = self.app.db[collection_name].find_one()['_id']
        response = self.client.get('/test/%s' % str(obj_id))
        self.assertEquals(response.status_code, 200)
        expected_data = {collection_name: {
            '_id': {"$oid": str(obj_id)}, 'name': "Record 0"}}
        self.assertEquals(response.json, expected_data)

    def test_get_instance_by_id_missing(self):
        obj_id = str(self.app.db[collection_name].find_one()['_id'])
        if obj_id[0] == 'a':
            obj_id = "b%s" % obj_id[1:]
        else:
            obj_id = "a%s" % obj_id[1:]
        response = self.client.get('/test/%s' % obj_id)
        self.assertEquals(response.status_code, 404)

    def test_get_instance_by_lookup(self):
        obj_id = self.app.db[collection_name].find_one()['_id']
        response = self.client.get('/test/Record 0')
        self.assertEquals(response.status_code, 200)
        expected_data = {collection_name: {
            '_id': {"$oid": str(obj_id)}, 'name': "Record 0"}}
        self.assertEquals(response.json, expected_data)

    def test_get_instance_by_lookup_missing(self):
        response = self.client.get('/test/Record 11')
        self.assertEquals(response.status_code, 404)

    @skip("Get instance lookup - 409")
    def test_get_instance_by_lookup_multiple(self):
        pass

    @skip("Get instance with limited fields")
    def test_get_instance_limit_fields(self):
        #Limit fields returned by instance
        pass

    @skip("Post request")
    def test_post(self):
        pass

    @skip("Post request with validation errors")
    def test_post_validation(self):
        pass

    @skip("Patch request")
    def test_patch(self):
        pass

    @skip("Patch request with validation errors")
    def test_patch_validation(self):
        pass

    @skip("Delete request")
    def test_delete(self):
        pass

    @skip("Delete request 404")
    def test_delete_missing(self):
        pass

    def _fixture_setup(self):
        for i in range(10):
            self.app.db[collection_name].insert(
                {'name': "Record %s" % i})
