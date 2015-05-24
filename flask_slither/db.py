# -*- coding: utf-8 -*-
from bson.objectid import ObjectId
from bson.errors import InvalidId
from pymongo import MongoClient
from uuid import UUID

import json
import logging


class JSONEncoder(json.JSONEncoder):
    """Encode all fancy mongo objects into normal strings. While it is useful
       in some cases to use the mongo json_util class, generally we want to
       hide complexity for the API client, and so don't return types. It is
       up to the API to convert incoming types, and up to this class to
       serialize all complex objects to standard JSON types"""

    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        if isinstance(obj, UUID):
            return str(obj).replace('-', '')
        return json.JSONEncoder.default(self, obj)


class MongoDbQuery():
    """This class encapsulates some method for querying the mongo database."""

    def __init__(self, **kwargs):
        self.collection = kwargs.get('collection', '')
        self.client = MongoClient(
            kwargs.get('DB_HOST', 'localhost'),
            kwargs.get('DB_PORT', 27017))
        db_name = kwargs.get('DB_NAME', 'testing_slither')
        self.db = self.client[db_name]

    def __exit__(self):
        self.db.close()

    def _clean_record(self, record):
        """Remove all fields with `None` values"""
        for k, v in dict(record).items():
            if isinstance(v, dict):
                v = self._clean_record(v)
            if v is None:
                record.pop(k)
        return record

    def get_instance(self, collection, obj_id, **kwargs):
        """Get a record from the database with the id field matching `obj_id`.
        """
        logging.info("Getting single record")
        try:
            obj_id = ObjectId(obj_id)
        except InvalidId:
            logging.error("Invalid ObjectId: {}".format(obj_id))
            return {}
        projection = kwargs.get('projection', {})
        projection = None if len(projection) < 1 else projection
        query = kwargs.get('query', {})
        query.update({'_id': obj_id})
        logging.debug("Query: {}".format(query))
        logging.debug("Projection: {}".format(projection))
        record = self.db[collection].find_one(query, projection)
        return record

    def get_collection(self, collection, **kwargs):
        """Get a record from the database with the id field matching `obj_id`.
        """
        query = kwargs.get('query', {})
        projection = kwargs.get('projection', {})
        projection = None if len(projection) < 1 else projection
        limit = kwargs.get('limit', 20)
        # sort = kwargs.get('sort', {})
        logging.info("About to get a collection from the database")
        logging.debug("Collection: {}".format(collection))
        logging.debug("Query: {}".format(query))
        logging.debug("Projection: {}".format(projection))
        logging.debug("Limit: {}".format(limit))
        records = \
            list(self.db[collection].find(query, projection).limit(limit))
        logging.debug("Got {} results".format(len(records)))
        return records

    def delete(self, collection, record):
        if record is not None and '_id' in record:
            logging.info("Deleting record: {}".format(record['_id']))
            self.db[collection].remove({'_id': record['_id']})

    def create(self, collection, record):
        logging.info("Creating new record")
        return self.db[collection].insert(self._clean_record(record))

    def update(self, collection, record, orig_record, full_update=False):
        logging.info("Updating record.")
        logging.debug("Full update? {}".format(full_update))
        if '_id' not in record:
            logging.warning("No id in record. Cannot update")
            logging.debug("Record: {}".format(record))
            return
        if len(record) < 1:
            logging.warning("Not updating empty record")
            return
        query = self._clean_record(record) if full_update else {'$set': record}
        record.pop('_id', '')
        _id = orig_record['_id']
        logging.debug("_id: {}".format(_id))
        logging.debug("Query: {}".format(query))
        self.db[collection].update({'_id': _id}, query)
        record['_id'] = _id
        return record

    def serialize(self, root, records):
        """Serialize the payload into JSON"""
        logging.info("Serializing record")
        logging.debug("Root: {}".format(root))
        logging.debug("Records: {}".format(records))
        if records == {}:
            return '{}'
        if isinstance(records, dict):
            if list(records.keys())[0] == 'errors':
                logging.warning("Found errors. Moving on".format(records))
                root = None
            elif '_id' in records:
                records['id'] = records.pop('_id')
        else:
            records = list(records)

            # rename _id to id
            for r in records:
                if '_id' in r:
                    r['id'] = r.pop('_id')

        if root is not None:
            records = {root: records}
        return json.dumps(records, cls=JSONEncoder)
