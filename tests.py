# -*- coding: utf-8 -*-
from contextlib import contextmanager
from datetime import datetime, timedelta
from flask import Flask, g
from flask.ext.testing import TestCase
from flask.ext.slither.authentication import RequestSigningAuthentication
from flask.ext.slither.authorization import ReadOnlyAuthorization
from flask.ext.slither.resources import BaseResource
from flask.ext.slither.signals import request_authenticated, post_create
from flask.ext.slither import register_api
from pymongo import MongoClient
from hashlib import sha1
from werkzeug.routing import BaseConverter

import binascii
import json
import hmac
import pytz

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


@contextmanager
def captured_auth_requests(app):
    recorded = []

    def record(sender, user, **extra):
        recorded.append(user)
    request_authenticated.connect(record, app)
    try:
        yield recorded
    finally:
        request_authenticated.disconnect(record, app)


@contextmanager
def captured_post_create(app):
    recorded = []

    def record(sender, **extra):
        recorded.append(extra)
    post_create.connect(record, app)
    try:
        yield recorded
    finally:
        post_create.disconnect(record, app)


class Resource(BaseResource):
    collection = collection_name

    def get(self, **kwargs):
        g.kwargs = kwargs
        return super(Resource, self).get(**kwargs)


class ReadOnlyAuthResource(BaseResource):
    collection = collection_name
    authorization = ReadOnlyAuthorization()


class RequestSigningAuthenticationResource(BaseResource):
    collection = collection_name
    authentication = RequestSigningAuthentication()


class BasicTestCase(TestCase):
    def create_app(self):
        app = Flask(__name__)
        app.url_map.converters['regex'] = RegexConverter

        app.config['DB_HOST'] = 'localhost'
        app.config['DB_PORT'] = 27017
        app.config['DB_NAME'] = 'test_slither'
        app.client = MongoClient(app.config['DB_HOST'], app.config['DB_PORT'])
        app.db = app.client[app.config['DB_NAME']]

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


class SimpleTestCase(BasicTestCase):
    def test_delete_by_id(self):
        obj_id = self.app.db[collection_name].find_one()['_id']
        count = self.app.db[collection_name].count()
        response = self.client.delete("/test/%s" % str(obj_id))
        self.assertEquals(response.status_code, 204)
        self.assertEquals(self.app.db[collection_name].count(), count - 1)

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
        with captured_post_create(self.app) as arqs:
            data = {collection_name: {
                'name': "post", "description": "success is good"}}
            response = self.client.post('/test', data=json.dumps(data),
                                        content_type="application/json")
            self.assertEquals(response.status_code, 201)
            obj = self.app.db[collection_name].find_one({'name': "post"})
            self.assertEquals(response.location,
                              "http://localhost/test/%s" % str(obj['_id']))
            self.assertEquals(len(arqs), 1)
            for k, v in data[collection_name].iteritems():
                self.assertEquals(arqs[0]['data'][k], v)
            self.assertFalse(arqs[0]['data']['_id'] is None)

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


class RequestSigningAuthenticationTestCase(BasicTestCase):
    def create_app(self):
        app = Flask(__name__)
        app.url_map.converters['regex'] = RegexConverter

        app.config['DB_HOST'] = 'localhost'
        app.config['DB_PORT'] = 27017
        app.config['DB_NAME'] = 'test_slither'
        app.config['TIMEZONE'] = 'Africa/Johannesburg'
        app.client = MongoClient(app.config['DB_HOST'], app.config['DB_PORT'])
        app.db = app.client[app.config['DB_NAME']]

        # register test resource
        register_api(app, RequestSigningAuthenticationResource, url="test")
        return app

    def headers(self, **kwargs):
        # Generate header for a valid request to the squire api
        url = "/localhost%s" % kwargs.get('url', "/test")
        auth_keys = self.app.db['users'].find_one()['auth']
        if '?' in url:
            url = url.split('?')[0]
        now = datetime.now(pytz.timezone(self.app.config['TIMEZONE'])) \
            .replace(microsecond=0)
        string_to_sign = (
            u"%(verb)s\n%(content-type)s\n%(content-md5)s\n"
            u"%(date)s\n%(resource)s") % {
                'verb': kwargs.get('verb', "GET").lower(),
                'content-type': kwargs.get('content-type', "application/json"),
                'content-md5': kwargs.get('content-md5', ""),
                'date': now, 'resource': url}
        self.app.logger.debug("T: String to sign: %s" % string_to_sign)
        a_key = str(kwargs.get('access_key', auth_keys['access_key']))
        s_key = str(kwargs.get('secret_key', auth_keys['secret_key']))
        hashed = hmac.new(s_key, string_to_sign, sha1)
        signature = binascii.b2a_base64(hashed.digest())[:-1]

        return {
            'content_type': "application/json",
            'headers': [('Authorization', "FS %s:%s" % (a_key, signature)),
            ('fs-date', kwargs.get('date', now))]}

    def test_no_authorization_header(self):
        self.app.logger.info("T: Sending request without authorization")
        response = self.client.get('/test')
        self.assertEquals(response.status_code, 401)
        self.assertEquals(response.json, "No authorization header")

    def test_no_FS(self):
        self.app.logger.info("T: Sending request without authorization")
        headers = [('Authorization', "test")]
        response = self.client.get('/test', headers=headers)
        self.assertEquals(response.status_code, 401)
        self.assertEquals(response.json, "Malformed authorization header")

    def test_no_date(self):
        self.app.logger.info("T: Sending request without date")
        headers = [('Authorization', "FS ")]
        response = self.client.get('/test', headers=headers)
        self.assertEquals(response.status_code, 401)
        self.assertEquals(response.json, "Missing date in header")

    def test_late_date(self):
        self.app.logger.info("T: Sending request with late date")
        now = datetime.now(pytz.timezone(self.app.config['TIMEZONE'])) \
            .replace(microsecond=0)
        late = now - timedelta(minutes=15, seconds=1)

        response = self.client.get('/test', **self.headers(date=late))
        self.assertEquals(response.status_code, 401)
        self.assertEquals(response.json, "Date is outside auth window period")

    def test_early_date(self):
        self.app.logger.info("T: Sending request with early date")
        now = datetime.now(pytz.timezone(self.app.config['TIMEZONE'])) \
            .replace(microsecond=0)
        early = now + timedelta(minutes=15, seconds=1)

        response = self.client.get('/test', **self.headers(date=early))
        self.assertEquals(response.status_code, 401)
        self.assertEquals(response.json, "Date is outside auth window period")

    def test_bad_access_key(self):
        self.app.logger.info("T: Sending request with bad access key")
        response = self.client.get('/test', **self.headers(access_key='asdf'))
        self.assertEquals(response.status_code, 401)
        self.assertEquals(response.json, "Access denied")

    def test_invalid_signature(self):
        self.app.logger.info("T: Sending request with bad signature")
        now = datetime.now(pytz.timezone(self.app.config['TIMEZONE'])) \
            .replace(microsecond=0)
        header = [('Authorization', "FS %s:%s" % ("access", "secret")),
                  ('Date', now)]
        response = self.client.get('/test', headers=header,
                                   content_type="application/json")
        self.assertEquals(response.status_code, 401)

    def test_success(self):
        self.app.logger.info("T: Sending successfully authenticated request")

        with self.app.test_client() as c:
            response = c.get('/test', **self.headers())
            self.assertEquals(response.status_code, 200)
            self.assertEquals(g.user['username'], 'testuser')

    def test_success_signal(self):
        self.app.logger.info("T: Testing signal for authenticated request")
        with captured_auth_requests(self.app) as arqs:
            self.app.test_client().get('/test', **self.headers())
            self.assertEquals(len(arqs), 1)
            self.assertEquals(arqs[0]['username'], "testuser")
