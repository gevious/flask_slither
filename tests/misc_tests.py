# -*- coding: utf-8 -*-
from flask import Flask, g, current_app
from flask.ext.testing import TestCase
from flask.ext.slither.authorization import ReadOnlyAuthorization
from flask.ext.slither.resources import BaseResource
from flask.ext.slither import register_api
from pymongo import MongoClient
from tests.default_tests import BasicTestCase, Resource, RegexConverter

import json

collection_name = 'tests'


class ReadOnlyAuthResource(BaseResource):
    collection = collection_name
    authorization = ReadOnlyAuthorization()


class NonstandardCollectionName(BasicTestCase):
    def create_app(self, **kwargs):
        return super(NonstandardCollectionName, self) \
            .create_app(ignore_resource=True)

    def setUp(self):
        super(NonstandardCollectionName, self).setUp()
        self.cn = 'nonstandard'

        class R(Resource):
            root_key = self.cn

        register_api(self.app, R, url="nstest")

    def test_delete(self):
        obj_id = self.app.db[collection_name].find_one()['_id']
        count = self.app.db[collection_name].count()
        self.assertFalse(self.app.db[collection_name].find_one(
            {'_id': obj_id}) is None)
        response = self.client.delete("/nstest/%s" % str(obj_id))
        self.assertEquals(response.status_code, 204)
        self.assertEquals(self.app.db[collection_name].count(), count - 1)
        self.assertTrue(self.app.db[collection_name].find_one(
            {'_id': obj_id}) is None)

    def test_get_instance(self):
        obj_id = self.app.db[collection_name].find_one()['_id']
        response = self.client.get('/nstest/%s' % str(obj_id))
        self.assertEquals(response.status_code, 200)
        expected_data = {self.cn: {
            '_id': {"$oid": str(obj_id)}, 'name': "Record 0",
            'extra': "Extra 0"}}
        self.assertEquals(response.json, expected_data)

    def test_get_list(self):
        response = self.client.get('/nstest')
        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.json.keys(), [self.cn])

    def test_patch(self):
        obj = self.app.db[collection_name].find_one({'name': "Record 4"})
        data = {self.cn: {'name': "patched"}}
        response = self.client.patch('/nstest/%s' % str(obj['_id']),
                                     data=json.dumps(data),
                                     content_type="application/json")
        self.assertEquals(response.status_code, 204)

    def test_post(self):
        data = {self.cn: {
            'name': "post", "description": "success is good"}}
        response = self.client.post('/nstest', data=json.dumps(data),
                                    content_type="application/json")
        self.assertEquals(response.status_code, 201)

    def test_put(self):
        obj = self.app.db[collection_name].find_one({'name': "Record 4"})
        data = {self.cn: {'name': "updated", 'extra': "winner"}}
        response = self.client.put('/nstest/%s' % str(obj['_id']),
                                   data=json.dumps(data),
                                   content_type="application/json")
        self.assertEquals(response.status_code, 204)


class UrlsTestCase(TestCase):
    """ Duplicated some of the simple tests, but with a different url. This
        is for testing embedded url params (eg a site name) in the path"""
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
        register_api(app, Resource, url=url)
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

    def test_get_list(self):
        with self.app.test_client() as c:
            response = c.get(self.url)
            self.assertEquals(response.status_code, 200)
            u_id = str(self.app.db['users'].find_one()['_id'])
            self.assertEquals(g.kwargs['company'], u_id)
            self.assertEquals(response.json.keys(), [collection_name])
            self.assertEquals(len(response.json[collection_name]), 10)
            for i in range(10):
                self.assertEquals(response.json[collection_name][i]['name'],
                                  "Record %s" % i)
                self.assertEquals(response.json[collection_name][i]['extra'],
                                  "Extra %s" % i)

    def test_get_list_invalid_url(self):
        self.url = "/%s" % self.url[2:]
        response = self.client.get(self.url)
        self.assertEquals(response.status_code, 404)

    def test_post(self):
        data = {collection_name: {
            'name': "post", "description": "success is good"}}
        response = self.client.post(self.url, data=json.dumps(data),
                                    content_type="application/json")
        self.assertEquals(response.status_code, 201)
        obj = self.app.db[collection_name].find_one({'name': "post"})
        self.assertEquals(response.location,
                          "http://localhost%s/%s" %
                          (self.url, str(obj['_id'])))
        r = self.client.get(response.location[len('http://localhost/'):])
        self.assertEquals(r.status_code, 200)


class AdvancedFunctionality(BasicTestCase):
    def create_app(self, **kwargs):
        return super(AdvancedFunctionality, self) \
            .create_app(ignore_resource=True)

    def test_get_instance_by_id(self):
        """ Ensure only the instance is returned for a wide access_limit range.
            Fixes #16"""

        rid = self.app.db[collection_name].find_one(
            {'name': "Record 1"})['_id']

        class R(Resource):
            def access_limits(self, **kwargs):
                return {'_id': rid}

        register_api(self.app, R, url="test")

        obj_id = self.app.db[collection_name].find_one(
            {'name': "Record 1"})['_id']
        response = self.client.get('/test/%s' % str(obj_id))
        self.assertEquals(response.status_code, 200)

        obj_id = self.app.db[collection_name].find_one(
            {'name': "Record 0"})['_id']
        response = self.client.get('/test/%s' % str(obj_id))
        self.assertEquals(response.status_code, 404)

    def test_get_collection_with_access_limits(self):
        """ Ensure only records within the access_limit range are returned
            Fixes #16"""

        class R(Resource):
            def access_limits(self, **kwargs):
                # limit list to Record 0 and Record 1
                ids = current_app.db[collection_name].find().limit(2)
                ids = [i['_id'] for i in ids]
                return {'_id': {'$in': ids}}

        register_api(self.app, R, url="test")

        response = self.client.get('/test')
        self.assertEquals(response.status_code, 200)

        self.assertEquals(len(response.json['tests']), 2)
        for i, u in enumerate(response.json['tests']):
            self.assertEquals(u['name'], "Record %s" % i)

    def test_get_instance_with_access_limits(self):
        """ Ensure only the instance is returned for a wide access_limit range.
            Fixes #16"""

        class R(Resource):
            def access_limits(self, **kwargs):
                # limit list to Record 0 and Record 1
                ids = current_app.db[collection_name].find().limit(2)
                ids = [i['_id'] for i in ids]
                return {'_id': {'$in': ids}}

        register_api(self.app, R, url="test")

        obj_id = self.app.db[collection_name].find_one(
            {'name': "Record 0"})['_id']
        response = self.client.get('/test/%s' % str(obj_id))
        self.assertEquals(response.status_code, 200)

        obj_id = self.app.db[collection_name].find_one(
            {'name': "Record 1"})['_id']
        response = self.client.get('/test/%s' % str(obj_id))
        self.assertEquals(response.status_code, 200)

        obj_id = self.app.db[collection_name].find_one(
            {'name': "Record 2"})['_id']
        response = self.client.get('/test/%s' % str(obj_id))
        self.assertEquals(response.status_code, 404)


class ReadOnlyAuthorizationTestCase(BasicTestCase):
    def create_app(self):
        app = Flask(__name__)
        app.url_map.converters['regex'] = RegexConverter

        app.config['DB_HOST'] = 'localhost'
        app.config['DB_PORT'] = 27017
        app.config['DB_NAME'] = 'test_slither'
        app.client = MongoClient(app.config['DB_HOST'], app.config['DB_PORT'])
        app.db = app.client[app.config['DB_NAME']]

        # register test resource
        register_api(app, ReadOnlyAuthResource, url="test")
        return app

    def test_get_list(self):
        response = self.client.get("/test")
        self.assertEquals(response.status_code, 200)

    def test_get_instance_by_id(self):
        obj_id = self.app.db[collection_name].find_one()['_id']
        response = self.client.get('/test/%s' % str(obj_id))
        self.assertEquals(response.status_code, 200)

    def test_get_instance_by_lookup(self):
        response = self.client.get("/test/Record 0")
        self.assertEquals(response.status_code, 200)

    def test_post(self):
        data = {collection_name: {
            'name': "post", "description": "success is good"}}
        count = self.app.db[collection_name].count()
        response = self.client.post('/test', data=json.dumps(data),
                                    content_type="application/json")
        self.assertEquals(response.status_code, 403)
        self.assertEquals(self.app.db[collection_name].count(), count)

    def test_patch(self):
        obj = self.app.db[collection_name].find_one({'name': "Record 4"})
        data = {collection_name: {'name': "patched"}}
        count = self.app.db[collection_name].count()
        response = self.client.patch('/test/%s' % str(obj['_id']),
                                     data=json.dumps(data),
                                     content_type="application/json")
        self.assertEquals(response.status_code, 403)
        self.assertEquals(self.app.db[collection_name].count(), count)

    def test_put(self):
        obj = self.app.db[collection_name].find_one({'name': "Record 4"})
        data = {collection_name: {'name': "updated", 'extra': "winner"}}
        count = self.app.db[collection_name].count()
        response = self.client.put('/test/%s' % str(obj['_id']),
                                   data=json.dumps(data),
                                   content_type="application/json")
        self.assertEquals(response.status_code, 403)
        self.assertEquals(self.app.db[collection_name].count(), count)

    def test_delete_by_id(self):
        obj_id = self.app.db[collection_name].find_one()['_id']
        count = self.app.db[collection_name].count()
        response = self.client.delete("/test/%s" % str(obj_id))
        self.assertEquals(response.status_code, 403)
        self.assertEquals(self.app.db[collection_name].count(), count)

    def test_delete_by_lookup(self):
        count = self.app.db[collection_name].count()
        response = self.client.delete("/test/Record 4")
        self.assertEquals(response.status_code, 403)
        self.assertEquals(self.app.db[collection_name].count(), count)
