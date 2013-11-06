# -*- coding: utf-8 -*-
from flask import Flask, g
from flask.ext.testing import TestCase
from flask.ext.slither.authorization import ReadOnlyAuthorization
from flask.ext.slither.resources import BaseResource
from flask.ext.slither import register_api
from pymongo import MongoClient
from werkzeug.routing import BaseConverter
from unittest import skip

import json

""" Vanilla extention of BaseAPI so we can test all BaseAPI functionality
as-is"""

collection_name = 'tests'


# Unfortunately we need to add the regex urlmapper here because I
# still need to figure out how to add it to the blueprint outside the
# app context
class RegexConverter(BaseConverter):
    def __init__(self, url_map, *items):
        super(RegexConverter, self).__init__(url_map)
        self.regex = items[0]


class Resource(BaseResource):
    collection = collection_name

    def get(self, **kwargs):
        g.kwargs = kwargs
        return super(Resource, self).get(**kwargs)


class ReadOnlyAuthResource(BaseResource):
    collection = collection_name
    authorization = ReadOnlyAuthorization()


class BasicTestCase(TestCase):
    def create_app(self, **kwargs):
        app = Flask(__name__)
        app.url_map.converters['regex'] = RegexConverter

        app.config['DB_HOST'] = 'localhost'
        app.config['DB_PORT'] = 27017
        app.config['DB_NAME'] = 'test_slither'
        app.client = MongoClient(app.config['DB_HOST'], app.config['DB_PORT'])
        app.db = app.client[app.config['DB_NAME']]

        if not kwargs.get('ignore_resource', False):
            # register test resource
            register_api(app, Resource, url="test")
        return app

    def setUp(self):
        # Insert test records
        for i in range(10):
            self.app.db[collection_name].insert(
                {'name': "Record %s" % i, 'extra': "Extra %s" % i})
        self.app.db['users'].insert(
            {'username': "testuser", 'auth': {
                'access_key': "super", 'secret_key': "duper"}})

    def tearDown(self):
        self.app.db[collection_name].drop()
        self.app.db['users'].drop()


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


class DefaultFunctionality(BasicTestCase):
    def test_delete_by_id(self):
        obj_id = self.app.db[collection_name].find_one()['_id']
        count = self.app.db[collection_name].count()
        self.assertFalse(self.app.db[collection_name].find_one(
            {'_id': obj_id}) is None)
        response = self.client.delete("/test/%s" % str(obj_id))
        self.assertEquals(response.status_code, 204)
        self.assertEquals(self.app.db[collection_name].count(), count - 1)
        self.assertTrue(self.app.db[collection_name].find_one(
            {'_id': obj_id}) is None)

    def test_delete_by_lookup(self):
        count = self.app.db[collection_name].count()
        response = self.client.delete("/test/Record 4")
        self.assertEquals(response.status_code, 204)
        self.assertEquals(self.app.db[collection_name].count(), count - 1)

    def test_delete_missing(self):
        response = self.client.delete("/test/missing")
        self.assertEquals(response.status_code, 404)

    def test_get_list(self):
        response = self.client.get('/test')
        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.json.keys(), [collection_name])
        self.assertEquals(len(response.json[collection_name]), 10)
        for i in range(10):
            self.assertEquals(response.json[collection_name][i]['name'],
                              "Record %s" % i)
            self.assertEquals(response.json[collection_name][i]['extra'],
                              "Extra %s" % i)

    def test_get_list_search(self):
        response = self.client.get('/test?where={"name": "Record 3"}')
        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.json.keys(), [collection_name])
        self.assertEquals(len(response.json[collection_name]), 1)
        self.assertEquals(response.json['tests'][0]['extra'], "Extra 3")

    def test_get_list_limit_fields(self):
        response = self.client.get('/test?_fields=name&_fields=wrong')
        self.assertEquals(response.status_code, 200)
        self.assertEquals(len(response.json[collection_name]), 10)
        for i in range(10):
            self.assertFalse('extra' in response.json[collection_name][i])

    def test_get_instance_by_id(self):
        obj_id = self.app.db[collection_name].find_one()['_id']
        response = self.client.get('/test/%s' % str(obj_id))
        self.assertEquals(response.status_code, 200)
        expected_data = {collection_name: {
            '_id': {"$oid": str(obj_id)}, 'name': "Record 0",
            'extra': "Extra 0"}}
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
            '_id': {"$oid": str(obj_id)}, 'name': "Record 0",
            'extra': "Extra 0"}}
        self.assertEquals(response.json, expected_data)

    def test_get_instance_by_lookup_missing(self):
        response = self.client.get('/test/Record 11')
        self.assertEquals(response.status_code, 404)

    def test_get_instance_by_lookup_multiple(self):
        obj = self.app.db[collection_name].find_one({'name': "Record 4"})
        self.app.db[collection_name].update(
            {'_id': obj['_id']}, {'name': 'Record 0'})
        self.assertEquals(self.app.db[collection_name]
            .find({'name': "Record 0"}).count(), 2)
        response = self.client.get('/test/Record 0')
        self.assertEquals(response.status_code, 409)

    def test_get_instance_limit_fields(self):
        obj = self.app.db[collection_name].find_one({'name': "Record 4"})
        response = self.client.get('/test/Record 4?_fields=extra')
        self.assertEquals(response.status_code, 200)
        expected_data = {collection_name: {
            '_id': {"$oid": str(obj['_id'])}, 'extra': "Extra 4"}}
        self.assertEquals(response.json, expected_data)

    def test_patch(self):
        obj = self.app.db[collection_name].find_one({'name': "Record 4"})
        data = {collection_name: {'name': "patched"}}
        response = self.client.patch('/test/%s' % str(obj['_id']),
                                     data=json.dumps(data),
                                     content_type="application/json")
        self.assertEquals(response.status_code, 204)
        obj = self.app.db[collection_name].find_one({'_id': obj['_id']})
        self.assertEquals(obj['name'], data[collection_name]['name'])

    def test_post(self):
        data = {collection_name: {
            'name': "post", "description": "success is good"}}
        response = self.client.post('/test', data=json.dumps(data),
                                    content_type="application/json")
        self.assertEquals(response.status_code, 201)
        obj = self.app.db[collection_name].find_one({'name': "post"})
        self.assertEquals(response.location,
                          "http://localhost/test/%s" % str(obj['_id']))
        for k, v in data[collection_name].iteritems():
            self.assertEquals(obj[k], v)

    def test_post_missing_collection(self):
        data = {'name': "post", "description": "success is good"}
        response = self.client.post('/test', json.dumps(data),
                                    content_type="application/json")
        self.assertEquals(response.status_code, 400)
        self.assertEquals(response.json, "No collection in payload")

    def test_put(self):
        obj = self.app.db[collection_name].find_one({'name': "Record 4"})
        data = {collection_name: {'name': "updated", 'extra': "winner"}}
        response = self.client.put('/test/%s' % str(obj['_id']),
                                   data=json.dumps(data),
                                   content_type="application/json")
        self.assertEquals(response.status_code, 204)
        obj = self.app.db[collection_name].find_one({'_id': obj['_id']})
        for k in ['name', 'extra']:
            self.assertEquals(obj[k], data[collection_name][k])

    def test_put_exclude_field(self):
        obj = self.app.db[collection_name].find_one({'name': "Record 4"})
        data = {collection_name: {'name': "updated"}}
        response = self.client.put('/test/%s' % str(obj['_id']),
                                   data=json.dumps(data),
                                   content_type="application/json")
        self.assertEquals(response.status_code, 204)
        obj = self.app.db[collection_name].find_one({'_id': obj['_id']})
        self.assertFalse('extra' in obj)

    def test_methods_unavailable(self):
        orig_allowed = Resource.allowed_methods
        for k in orig_allowed:
            allowed_methods = list(orig_allowed)
            allowed_methods.remove(k)
            Resource.allowed_methods = allowed_methods
            func = getattr(self.client, k.lower())
            response = func('/test')
            self.assertEquals(response.status_code, 405, "Error in %s" % k)
        Resource.allowed_methods = orig_allowed


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


class CorsResource(BaseResource):
    collection = collection_name
    allowed_methods = ['GET', 'POST', 'PUT', 'PATCH', 'OPTIONS']


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
