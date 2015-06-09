# -*- coding: utf-8 -*-
from flask import make_response, request, g, current_app, json, abort
from flask.views import MethodView
from flask_slither.decorators import endpoint, crossdomain
from flask_slither.db import MongoDbQuery

import time


class BaseResource(MethodView):

    #: A list of HTTP methods that are open for use. Any method not on this
    #: list will return a 405 if accessed."""
    allowed_methods = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']

    #: This is the database table/collection name that this resource will
    #: access by default
    db_collection = None

    #: This class is used for all database queries as well as serialization
    #: of the final records
    db_query = MongoDbQuery

    #: By default request bodies must have the db_collection name as the root
    #: field. Set this to false if not the case
    enforce_json_root = True

    #: Set the json_root manually if it is something other than db_collection
    # json_root = self.db_collection

    #: POST/PUT/PATCH requests must have the root of the data equal to the
    #: `db_collection`. If this is false, it is not enforced
    enforce_payload_collection = True

    #: If an authentication class is defined, it can contain the methods
    #: `is_authenticated` and `is_authorized` which will contain the logic
    #: to check if the request has access to the resource. If the methods
    #: aren't defined, it is assumed that authentication/authorization is
    #: successful.
    authentication = None

    #: If a validation class is defined, the `validate_<type>` method will be
    #: used to validate the type of request (e.g. GET, POST etc). Validation
    #: is assumed to pass if no method is defined.
    validation = None

    #: Allow CORS requests, and if True, put in extra parameters
    cors_enabled = False
    cors_config = {
        'max_age': 21600,
        'methods': ["GET", "POST", "PUT", "PATCH", "DELETE"],
        'allowed': None,
        'blacklist': [],
        'headers': None
    }

    def __init__(self, app=None, **kwargs):
        if app is not None:
            self.app = app
            self.init_app(self.app)
        else:
            self.app = None
        self.db_query = self.db_query(**current_app.config)

    def init_app(self, app):
        app.teardown_appcontext(self.teardown)

    def _exception_handler(self, e):
        """This exception handler catches should only be invoked when we need
           to quit the workflow prematurely. It takes in an `ApiException`
           which will contain the error, details of the error and  status code.
           When the application is in testing mode, it will also return the
           stack trace"""
        if isinstance(e.message, dict):
            return self._prep_response(
                e.message['msg'], status=e.message['status'])
        if e.message.find('Validation') == 0:
            return self._prep_response(self.validation.errors, status=400)
        elif e.message.find('No record') == 0:
            return self._prep_response(status=404)
        else:
            return self._prep_response({'message': e.message},
                                       status=409)

    def _get_instance(self, **kwargs):
        """Loads the record specified by the `obj_id` path in the url and
           stores it in g._resource_instance"""
        current_app.logger.info("Getting instance")
        current_app.logger.debug("kwargs: {}".format(kwargs))

        current_app.logger.info(
            "Loading instance: {}".format(kwargs['obj_id']))
        rec = self.db_query.get_instance(self.db_collection, kwargs['obj_id'])
        g._resource_instance = rec
        current_app.logger.debug(
            "g._resource_instance: {}".format(g._resource_instance))
        return rec

    def _payload_root(self):
        """ Returns the expected json root in the payload"""
        if hasattr(self, 'json_root'):
            return self.json_root
        return self.db_collection

    def _make_response(self, status, data=None, **kwargs):
        if kwargs.get('is_file', False):
            current_app.logger.info("Setting response from first parameter")
            response = data
        else:
            current_app.logger.info("Generating response and sending")
            current_app.logger.debug("Status: {}".format(status))
            current_app.logger.debug("Data: {}".format(data))
            has_errors = str(status)[0] in ['4', '5']
            if has_errors:
                current_app.logger.debug("Returning errors payload")
                if isinstance(data, dict):
                    payload = data if 'errors' in list(data.keys() or '') \
                        else {'errors': data}
                else:
                    payload = {'errors': data}
                payload = self.db_query.serialize(None, payload)
            else:
                if kwargs.get('no_serialize', False):
                    payload = data
                else:
                    payload = "" if data is None else \
                        self.db_query.serialize(self._payload_root(), data)
            current_app.logger.debug("Payload: {}".format(payload))
            response = make_response(payload, status)

            current_app.logger.info("Adding response headers")
            response.headers.add('Cache-Control',
                                 'max-age={},must-revalidate'.format(30))
            if data is None and kwargs.get('mimetype', None) is None:
                kwargs['mimetype'] = 'text/plain'

            response.mimetype = kwargs.get('mimetype', 'application/json')
            for h in kwargs.get('headers', []):
                response.headers.add(h[0], h[1])
            if request.method == 'POST' and not has_errors and status == 201:
                location = "{}/{}".format(self._url, data['id'])
                response.headers.add('location', location)
            response.expires = time.time() + 30
            current_app.logger.debug("Headers: {}".format(response.headers))
        if kwargs.get('abort', False):
            abort(response)
        return response

    def fiddle_id(self, obj_id):
        """In some cases the `obj_id` in the url doesn't exactly match the
           record id. This method allows for the fiddling of the id to match
           the correct record."""
        return obj_id

    def transform_record(self, request_data):
        """A hook for changing the request data into something that should
           be persisted in the database"""
        return request_data

    def transform_payload(self, payload):
        """A hook for the user to transform the payload before it is sent
           back to the client."""
        return payload

    def post_save(self, record):
        """Hook called after a record is saved."""
        pass

    def post_delete(self, record):
        """Hook called after a record is deleted."""
        pass

    def merge_record_data(self, changes, orig_record=None):
        """This method merges PATCH requests with the db record to ensure no
           data is lost. In addition, it is also a hook for other fields to
           be overwritten, to ensure immutable fields aren't changed by a
           request."""
        current_app.logger.info("Merging request data with db record")
        current_app.logger.debug("orig_record: {}".format(orig_record))
        current_app.logger.debug("Changes".format(changes))
        final_record = changes
        if request.method == 'PATCH':
            final_record = dict(orig_record)
            final_record.update(changes)
        elif request.method == 'PUT':
            if '_id' in orig_record:
                final_record['_id'] = orig_record['_id']
        return final_record

    def access_limits(self, **kwargs):
        """This method returns a base query to be used for db queries"""
        return {}

    def limit_fields(self, **kwargs):
        """This method returns the projections for this resource"""
        return {}

    @crossdomain
    @endpoint
    def get(self, **kwargs):
        current_app.logger.info("GETting record(s) from database")
        records = []

        # generate meta information
        params = {'query': self.access_limits(**kwargs), 'projection': {}}
        if '_limit' in request.args:
            try:
                params['limit'] = int(request.args.get('_limit'))
            except ValueError:
                current_app.logger.debug("No record limit override")
                pass
        if '_fields' in request.args:
            params['projection'] = \
                {r: True for r in request.args.get('_fields', '').split(',')}
        params['projection'].update(self.limit_fields(**kwargs))

        if 'obj_id' in kwargs:
            records = self.db_query.get_instance(
                self.db_collection, kwargs['obj_id'], **params)
            if records in [{}, None]:
                return self._make_response(404)
        else:
            records = \
                self.db_query.get_collection(self.db_collection, **params)

        return self._make_response(200, self.transform_payload(records))

    @crossdomain
    @endpoint
    def post(self, **kwargs):
        current_app.logger.info("POSTing record to database")
        current_app.logger.debug(g._saveable_record)
        record_id = self.db_query.create(self.db_collection,
                                         g._saveable_record)
        record = self.db_query.get_instance(self.db_collection, record_id)
        self.post_save(record)
        return self._make_response(201, record)

    @crossdomain
    @endpoint
    def put(self, **kwargs):
        current_app.logger.info("PUTting record to database")
        current_app.logger.debug(g._saveable_record)
        record = self.db_query.update(self.db_collection, g._saveable_record,
                                      orig_record=g._resource_instance,
                                      full_update=True)
        self.post_save(record)
        return self._make_response(204)

    @crossdomain
    @endpoint
    def patch(self, **kwargs):
        current_app.logger.info("PATCHing record to database")
        current_app.logger.debug(g._saveable_record)
        record = self.db_query.update(self.db_collection, g._saveable_record,
                                      orig_record=g._resource_instance)
        self.post_save(record)
        return self._make_response(204)

    @crossdomain
    @endpoint
    def delete(self, **kwargs):
        current_app.logger.info("DELETEing record from database")
        self.db_query.delete(self.db_collection, g._resource_instance)
        self.post_delete(g._resource_instance)
        return self._make_response(204)

    @crossdomain
    def options(self, **kwargs):
        """This method has been implemented as per the CORS spec, however is
        not accessible by default. To included it make `cors_enabled` = True"""
        if self.cors_enabled:
            return self._make_response(200)
        return self._make_response(405, "CORS request rejected")
