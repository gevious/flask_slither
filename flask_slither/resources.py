# -*- coding: utf-8 -*-
from __future__ import with_statement

from bson.objectid import ObjectId
from bson import json_util
from datetime import datetime
from flask import current_app, abort, request, make_response, g, redirect
from flask.views import MethodView
from flask.ext.slither.authentication import NoAuthentication
from flask.ext.slither.authorization import NoAuthorization
from flask.ext.slither.decorators import preflight_checks, crossdomain
from flask.ext.slither.exceptions import ApiException
from flask.ext.slither.validation import NoValidation

import pymongo
import re
import time


class BaseResource(MethodView):
    model = None
    lookup_field = 'name'
    DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

    """ The authentication class has one method called `is_authenticated` and
    returns True or False depending on whether the request is authenticated or
    not. If not, a 401 is returned, otherwise the process continues"""
    authentication = NoAuthentication()

    """ The authorization class has one method called `is_authorized`. It
    determines if the user issuing the request is authorized to make this
    request. If not a 403 is returned. """
    authorization = NoAuthorization()

    """ The collection name this api is responsible for. This *must* be
    defined in a child class otherwise mongo won't know which collection to
    use for its transactions."""
    collection = None

    """ The `validation` method gets called and stores the
    errors in a dict called `errors`."""
    validation = NoValidation()

    """ A list of HTTP methods that are open for use. Any method not on this
    list will return a 405 if accessed."""
    allowed_methods = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']

    """By default all POST and PUT methods must have their payloads wrapped
       in the collection name. Setting this to `False` will prevent the
       default behaviour"""
    enforce_payload_collection = True

    """By default the json base key is the collection name. However by changing
       this value, it will become the root key of every request"""
    root_key = collection

    """Always return payload matching updated instance. More fine-grain
       control can be achieved but setting `always_return_payload_<VERB>` where
       <VERB> is either post, put or patch"""
    always_return_payload = False
    always_return_payload_post = True

    """Allow cors requests"""
    cors_enabled = False

    """Maximum time a CORS requests can live before having to re-establish
       their validity (in seconds)"""
    cors_max_age = 21600

    """Methods allowed by CORS requests. The default allows all methonds.
       Note: CORS is only enabled if the `OPTIONS` method is allowed in
       `allowed_methods`. It is disabled by default."""
    cors_methods = ["GET", "POST", "PUT", "PATCH", "DELETE"]

    """A list of origins from which the API may accept requests. If it is None,
       then all origins (except blacklisted ones) are accepted"""
    cors_allowed = None

    """Any request from a blacklisted origin won't be allowed to connect to the
       API. This takes precidence over the allowed origins"""
    cors_blacklist = []

    """Specify particular headers that are allowed in CORS requests. Defaults
       to all."""
    cors_headers = None

    def __init__(self, app=None):
        if app is not None:
            self.app = app
            self.init_app(self.app)
        else:
            self.app = None

    def init_app(self, app):
        # Use the newstyle teardown_appcontext if it's available,
        # otherwise fall back to the request context
        if hasattr(app, 'teardown_appcontext'):
            app.teardown_appcontext(self.teardown)
        else:
            app.teardown_request(self.teardown)

    def _get_root(self):
        """ Returns the expected json root in the payload"""
        if getattr(self, 'root_key') and self.root_key is not None:
            return self.root_key
        return self.collection

    def _link(self, rel, **kwargs):
        title = kwargs.get('title', self.collection[:-1].title())
        obj_id = kwargs.get('obj_id', "")
        obj_id = "" if obj_id == "" else "/%s" % obj_id
        prefix = current_app.blueprints[request.blueprint].url_prefix
        prefix = "" if prefix is None else prefix
        # TODO: figure out to get this 1.0 prefix from the blueprint url_prefix
        prefix = "/1.0"
        return ('<link rel="%(rel)s" title="%(title)s" '
                'href="%(prefix)s/%(collection)s%(obj_id)s" />') % \
            {'rel': rel, 'title': title, 'prefix': prefix,
             'collection': self.collection, 'obj_id': obj_id}

    def _datetime_parser(self, dct):
        for k, v in dct.items():
            # TODO: update regex to match time better
            if isinstance(v, basestring) and re.search("\ UTC", v):
                try:
                    dct[k] = datetime.strptime(v, self.DATE_FORMAT)
                except:
                    # this is a normal string
                    pass
        return dct

    def _exception_handler(self, e):
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

    ######################################
    # Preparing response into proper mime
    def _prep_response(self, dct={}, last_modified=None, etag=None,
                       status=200, **kwargs):
        if str(status)[0] == '2' and hasattr(self, 'redirect'):
            return redirect(self.redirect)
        # TODO: handle more mime types
        mime = "application/json"
        rendered = json_util.dumps(dct)
    #    rendered = globals()[render](**dct)
        resp = make_response(rendered, status)
        resp.headers.add('Cache-Control',
                         'max-age=%s,must-revalidate' % 30)
        # todo, make this variable
        current_app.logger.warning("Change the origin policy")
        resp.headers.add('Access-Control-Allow-Origin',
                         request.headers.get('origin', '*'))
        for h in kwargs.get('headers', []):
            resp.headers.add(h[0], h[1])
        resp.expires = time.time() + 30
        if etag:
            resp.headers.add('ETag', etag)
        if last_modified:
            resp.headers.add('Last-Modified',
                             self._datetime_parser(last_modified))
        if rendered != "":
            resp.mimetype = mime
        return resp

    def access_limits(self, **kwargs):
        """ Returns a query which filters the current collection based on
        authentication access"""
        return {}

    def delete_query(self, **kwargs):
        obj = self._get_instance(**kwargs)[self._get_root()]
        return obj['_id']

    def limit_fields(self, **kwargs):
        """A set of fields used mongo query. Fields can be passed in the
        query, but listing them here sets fields up as default. Useful if
        you want a subset of fields for an object every time except in
        unusual circumstances, eg {'password': 0}"""
        return {}

    def get_location(self, obj_id, **kwargs):
        """Generate the location uri for POST 201 response"""
        # Swap placeholders in url with actual values
        location = self._url
        for k, v in kwargs.iteritems():
            idx = location.find(k)
            if idx < 0:
                continue
            start_idx = location.rfind('/', 0, idx)
            end_idx = location[idx:].find('/') + idx
            location = "%s%s%s" % \
                (location[:start_idx], v, location[end_idx:])
        if hasattr(current_app, 'api_version'):
            location = "{}{}".format(current_app.api_version, location)
        return '%s/%s' % (location, obj_id)

    def post_save(self, **kwargs):
        """ A hook to run other code that depends on successful post"""
        pass

    def post_delete(self, **kwargs):
        """ A hook to run other code that depends on successful delete"""
        pass

    def pre_validation_transform(self,  **kwargs):
        """ Transform the data by adding or removing fields before the
        data is validated. Useful for adding server generated fields, such
        as an author for a post. We assume that all fields are mongo references
        since mostly they will be"""
        data = g.s_data
#        for k, v in g.s_data.iteritems():
#            if isinstance(v, dict) and '$oid' in v:
#                g.s_data[k] = ObjectId(v['$oid'])
        for k, v in kwargs.iteritems():
            if k in ['obj_id', '_lookup']:
                continue
            data[k] = ObjectId(v)
        return data

    def transform_payload(self, payload):
        """Any final payload transformation is done over here"""
        return payload

    def _get_collection(self, **kwargs):
        current_app.logger.debug("GETting collection")
        documents = []
        try:
            query = {} if 'where' not in request.args else \
                json_util.loads(request.args.get('where'))
            query.update(self.access_limits(**kwargs))
            cursor = current_app.db[self.collection] \
                .find(query, self._get_projection())
            if 'sort' in request.args:
                sort = []
                for k, v in json_util.loads(request.args['sort']).iteritems():
                    sort.append(
                        (k, pymongo.ASCENDING if v else pymongo.DESCENDING))
                cursor = cursor.sort(sort)
            documents = list(cursor)
        except ValueError:
            abort(400)

        return {self._get_root(): documents}

    def _get_instance(self, **kwargs):
        current_app.logger.debug("GETting instance")

        al = self.access_limits(**kwargs)
        if 'obj_id' in kwargs:
            query = {'_id': ObjectId(kwargs['obj_id'])}
        else:
            query = {self.lookup_field: kwargs['_lookup']}

        if query.keys()[0] in al.keys():
            # and the clashing values together
            k = query.keys()[0]
            query['$and'] = [] if '$and' not in query else query['$and']
            query['$and'].extend([{k: query[k]}, {k: al[k]}])
            del query[k]
        else:
            query.update(al)

        count = current_app.db[self.collection].find(query).count()
        if count < 1:
            raise ApiException("No record found for this lookup")
        elif count > 1:
            raise ApiException("Multiple records found for this lookup")
        g.s_instance = current_app.db[self.collection] \
            .find_one(query, self._get_projection())
        return {self._get_root(): g.s_instance}

    def _get_projection(self):
        projection = {}
        if '_fields' in request.args:
            projection = {}
            for k in request.args.getlist('_fields'):
                projection[k] = 1
        final = self.limit_fields()
        final.update(projection)
        return None if final == {} else final

    def _validate(self, **kwargs):
        method = 'validate_%s' % request.method.lower()
        if not hasattr(self.validation, method):
            current_app.logger.warning("No validation performed")
            return

        getattr(self.validation, method)(
            model=self.model, collection=self.collection, **kwargs)

        if len(self.validation.errors) > 0:
            raise ApiException("Validation")

    @crossdomain
    @preflight_checks
    def delete(self, **kwargs):
        kwargs['is_instance'] = True

        try:
            self._validate(**kwargs)
            current_app.db[self.collection].remove(self.delete_query(**kwargs))
            self.post_delete(collection=self.collection, **kwargs)
            return self._prep_response(status=204)
        except ApiException, e:
            return self._exception_handler(e)

    @crossdomain
    @preflight_checks
    def get(self, **kwargs):
        """ GET request entry point. We split the request into 2 paths:
            Getting a specific instance, either by id or lookup field
            Getting a list of records"""
        current_app.logger.debug("kwargs: %s" % kwargs)
        if '_lookup' in kwargs or 'obj_id' in kwargs:
            kwargs['is_instance'] = True
        try:
            self._validate(**kwargs)
            method = '_get_'
            method += 'instance' if 'is_instance' in kwargs else 'collection'
            payload = getattr(self, method)(**kwargs)
            payload = self.transform_payload(payload)
            if getattr(self, 'get_raw_payload', False):
                return payload
            return self._prep_response(payload)
        except ApiException, e:
            return self._exception_handler(e)

    @crossdomain
    @preflight_checks
    def patch(self, **kwargs):
        try:
            self._get_instance(**kwargs)[self._get_root()]
            current_app.logger.debug("Obj pre change: %s" % g.s_instance)
            change = self.pre_validation_transform(**kwargs)
            if change == {}:
                return self._prep_response({}, status=204)
            final = g.s_instance.copy()
            final.update(change)
            self._validate(data=final, **kwargs)
            current_app.db[self.collection].update(
                {"_id": g.s_instance['_id']}, {"$set": change})
            self.post_save(collection=self.collection, change=change)
            if self.always_return_payload \
                    or getattr(self, 'always_return_payload_patch', False):
                return self._prep_response(g.s_instance, status=200)
            return self._prep_response(status=204)
        except ApiException, e:
            return self._exception_handler(e)

    @crossdomain
    @preflight_checks
    def post(self, **kwargs):
        try:
            g.s_instance = self.pre_validation_transform(**kwargs)
            self._validate(data=g.s_instance, **kwargs)
            is_update = '_id' in g.s_instance
            obj_id = current_app.db[self.collection].save(g.s_instance)

            self.post_save(collection=self.collection)
            location = self.get_location(obj_id, **kwargs)

            current_app.logger.warning("Formatting return payload")
            g.s_instance['_id'] = obj_id
            data = {self._get_root(): g.s_instance}
            if is_update:
                if not self.always_return_payload \
                        and not getattr(self, 'always_return_payload_post',
                                        False):
                    data = {}
                return self._prep_response(data)

            if self.always_return_payload \
                    or getattr(self, 'always_return_payload_post', False):
                return self._prep_response(data, status=201,
                                           headers=[('Location', location)])
            return self._prep_response(status=201,
                                       headers=[('Location', location)])
        except ApiException, e:
            return self._exception_handler(e)

    @crossdomain
    @preflight_checks
    def put(self, **kwargs):
        try:
            self._get_instance(**kwargs)[self._get_root()]

            change = self.pre_validation_transform(**kwargs)
            self._validate(data=change, **kwargs)
            query = {'$set': change, '$unset': {}}

            # Remove all fields not included in PUT request
            for k in g.s_instance.keys():
                if k not in change and k != '_id':
                    query['$unset'][k] = 1
            if query['$unset'] == {}:
                query.pop('$unset')

            current_app.db[self.collection].update(
                {"_id": g.s_instance['_id']}, query)
            change['_id'] = g.s_instance['_id']
            self.post_save(change=change)
            if self.always_return_payload \
                    or getattr(self, 'always_return_payload_put', False):
                return self._prep_response(g.s_instance, status=200)
            return self._prep_response(status=204)
        except ApiException, e:
            return self._exception_handler(e)

    @crossdomain
    def options(self, **kwargs):
        """This method has been implemented as per the CORS spec, however is
        not accessible by default. To included it make `cors_enabled` = True"""
        if self.cors_enabled:
            return self._prep_response()
        return self._prep_response("CORS request rejected", status=405)
