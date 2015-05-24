# -*- coding: utf-8 -*-
# The minimal test setup consists of a basic resource linked to a mongo
# database. Only the most basic functions are tested, without authentication
# or validation. It is designed to mimic a basic out-the-box resource and
# ensure that works as expected.

from bson.objectid import ObjectId
from flask import Flask
from flask_slither import register_resource
from flask_slither.resources import BaseResource
from pymongo import MongoClient

import json
import unittest


class MinimalResource(BaseResource):
    db_collection = 'minimals'


class MinimalTest(unittest.TestCase):

    def setUp(self):
        self.app = Flask('Minimal')
        self.app.config['TESTING'] = True
        self.app.config['DB_NAME'] = 'testing_slither'
        self.client = self.app.test_client()
        register_resource(self.app, MinimalResource)

        self.db_client = MongoClient('localhost', 27017)
        self.db = self.db_client[self.app.config['DB_NAME']]
        self._load_fixtures()

    def tearDown(self):
        self.db['minimals'].drop()
        self.db_client.close()
        self.client = None
        self.app = None

    def _load_fixtures(self):
        fixtures = [
            {'name': "Min1"},
            {'name': "Min2", 'numbers': [1, 2, 3]},
            {'name': "Min3", 'references': {'Min1': None, 'Min2': 'numbers'}},
        ]
        for f in fixtures:
            self.db['minimals'].insert(f)

    def test_get_collection(self):
        """Get basic collection"""
        r = self.client.get('/minimals')
        self.assertEquals(r.status_code, 200)
        records = json.loads(r.data.decode('utf-8'))
        self.assertEquals(list(records.keys()), ['minimals'])
        self.assertEquals(len(records['minimals']), 3)

    def test_get_collection_limited(self):
        """Get basic collection limited to 2"""
        r = self.client.get('/minimals?_limit=2')
        self.assertEquals(r.status_code, 200)
        records = json.loads(r.data.decode('utf-8'))
        self.assertEquals(list(records.keys()), ['minimals'])
        self.assertEquals(len(records['minimals']), 2)

    def test_get_collection_projection(self):
        """Get basic collection with a projection"""
        r = self.client.get('/minimals?_fields=name,numbers')
        self.assertEquals(r.status_code, 200)
        records = json.loads(r.data.decode('utf-8'))
        self.assertEquals(list(records.keys()), ['minimals'])
        self.assertEquals(len(records['minimals']), 3)
        for r in records['minimals']:
            k = list(r.keys())
            self.assertTrue('name' in k)
            if r['name'] == 'Min2':
                self.assertTrue('numbers' in k,
                                "Numbers in {}".format(r['name']))
            else:
                self.assertFalse('numbers' in k,
                                 "Numbers not in {}".format(r['name']))
            self.assertTrue('references' not in k,
                            "References not in {}".format(r['name']))

    def test_get_instance(self):
        """Get instance"""
        obj = self.db['minimals'].find_one({})

        r = self.client.get('/minimals/{}'.format(obj['_id']))
        self.assertEquals(r.status_code, 200)
        records = json.loads(r.data.decode('utf-8'))
        self.assertEquals(list(records.keys()), ['minimals'])
        obj['id'] = str(obj.pop('_id'))
        self.assertEquals(records['minimals'], obj)

    def test_get_instance_missing(self):
        """Get instance which doesn't exist"""
        r = self.client.get('/minimals/1')
        self.assertEquals(r.status_code, 404)

    def test_delete_instance(self):
        """Delete instance"""
        obj = self.db['minimals'].find_one({})

        r = self.client.delete('/minimals/{}'.format(obj['_id']))
        self.assertEquals(r.status_code, 204)
        self.assertEquals(self.db['minimals'].find().count(), 2)
        self.assertIsNone(self.db['minimals'].find_one({'_id': obj['_id']}))

    def test_delete_instance_missing(self):
        """Delete instance which doesn't exist"""
        r = self.client.get('/minimals/1')
        self.assertEquals(r.status_code, 404)
        self.assertEquals(self.db['minimals'].find().count(), 3)

    def test_post(self):
        """Add new record"""
        data = {'name': "New data", 'subcol': {'first': 1, 'second': 2}}
        r = self.client.post('/minimals', data=json.dumps({'minimals': data}),
                             content_type="application/json")
        self.assertEquals(r.status_code, 201)
        self.assertEquals(self.db['minimals'].find().count(), 4)

        response_record = json.loads(r.data.decode('utf-8'))['minimals']
        self.assertEquals(
            r.location,
            "http://localhost/minimals/{}".format(response_record['id']))

        db_rec = self.db['minimals'].find_one(
            {'_id': ObjectId(response_record['id'])})
        self.assertIsNotNone(db_rec)
        for k in ['name', 'subcol']:
            self.assertEquals(db_rec[k], data[k])
            self.assertEquals(response_record[k], data[k])

    def test_post_missing_collection(self):
        """Add new record but payload is misformed"""
        data = {'name': "New data", 'subcol': {'first': 1, 'second': 2}}
        r = self.client.post('/minimals', data=json.dumps(data),
                             content_type="application/json")
        self.assertEquals(r.status_code, 400)
        self.assertEquals(json.loads(r.data.decode('utf-8'))['errors'],
                          'Invalid JSON root in request body')

    def test_patch(self):
        """Update record with PATCH"""
        obj = self.db['minimals'].find_one({'name': 'Min3'})
        data = {'name': "Patched record"}
        self.assertFalse(obj['name'] == data['name'])

        r = self.client.patch('/minimals/{}'.format(obj['_id']),
                              data=json.dumps({'minimals': data}),
                              content_type="application/json")
        self.assertEquals(r.status_code, 204)
        self.assertEquals(self.db['minimals'].find().count(), 3)

        obj = self.db['minimals'].find_one({'_id': obj['_id']})
        self.assertEquals(obj['name'], data['name'])
        self.assertTrue('references' in obj)

    def test_put(self):
        """Update record with PUT"""
        obj = self.db['minimals'].find_one({'name': 'Min3'})
        data = {'name': "Patched record", 'extra': "field"}
        self.assertFalse(obj['name'] == data['name'])

        r = self.client.put('/minimals/{}'.format(obj['_id']),
                            data=json.dumps({'minimals': data}),
                            content_type="application/json")
        self.assertEquals(r.status_code, 204)
        self.assertEquals(self.db['minimals'].find().count(), 3)

        obj = self.db['minimals'].find_one({'_id': obj['_id']})
        self.assertEquals(obj['name'], data['name'])
        print(obj)
        print('references' in obj)
        self.assertFalse('references' in obj)
        self.assertEquals(obj['extra'], data['extra'])
