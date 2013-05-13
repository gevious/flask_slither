# -*- coding: utf-8 -*-
"""
    flaskext.slither
    ~~~~~~~~~~~~~~~~

    Flask extension for quickly building RESTful API endpoints from MongoDB.

    :copyright: (c) 2010 by Dan Jacob.
    :license: MIT, see LICENSE for more details.
"""

from __future__ import with_statement

__version__ = '0.1'

#from api.decorators import authenticate
from bson.objectid import ObjectId
from bson import json_util
from datetime import datetime
from flask import current_app, abort, request, make_response, g, Response
from flask.views import MethodView
from flask.ext.slither.authentication import NoAuthentication
from flask.ext.slither.authorization import NoAuthorization
from flask.ext.slither.exceptions import ApiException
from flask.ext.slither.validation import NoValidation
from mongokit.schema_document import RequireFieldError
from mongokit.document import Document
from urllib import urlencode
from functools import wraps

import pymongo
import re
import time


def preflight_checks(f):
    """ This decorator does any checks before the request is allowed through.
    This includes authentication, authorization, throttling and caching."""
    @wraps(f)
    def decorator(self, *args, **kwargs):
        current_app.logger.debug("%s request received" %
                                 request.method.upper())
        if not self.authentication.is_authenticated():
            current_app.logger.warning("Unauthenticated request")
            return self._prep_response(status=401)
        if not self.authorization.is_authorized():
            current_app.logger.warning("Unauthorized request")
            return self._prep_response(status=403)
        g.access_limits = self.authorization.access_limits()
        if self.collection is None:
            return self._prep_response("No collection defined",
                                       status=424)
        return f(self, *args, **kwargs)
    return decorator


class BaseEndpoints(MethodView):
    model = None
    require_site_filter = True  # usually all queries must contain site filter
    lookup_field = 'name'
    DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

    """ The authentication class has one method called `is_authenticated` and
    returns True or False depending on whether the request is authenticated or
    not. If not, a 401 is returned, otherwise the process continues"""
    authentication = NoAuthentication()

    """ The authorization class has two methods. The first, `is_authorized`
    determines if the user issuing the request is authorized to make this
    request. If not a 403 is returned. If the request is authorised, the
    `access_limits` function is called, which should return a query that limits
    the records the request has access to. This query will be used in
    conjuction with any other queries generated or used by the request"""
    authorization = NoAuthorization()

    """ The collection name this api is responsible for. This *must* be
    defined in a child class otherwise mongo won't know which collection to
    use for its transactions."""
    collection = None

    """ The validation class can transform a payload just before validation
    using the `pre_validation_transform` method which returns the new data
    dict. After that the `validation` method gets called and stores the
    errors in a dict called `errors`."""
    validation = NoValidation()

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

    def _link(self, rel, **kwargs):
        title = kwargs.get('title', self.collection[:-1].title())
        obj_id = kwargs.get('obj_id', "")
        obj_id = "" if obj_id == "" else "/%s" % obj_id
        prefix = current_app.blueprints[request.blueprint].url_prefix
        prefix = "" if prefix is None else prefix
        #TODO: figure out to get this 1.0 prefix from the blueprint url_prefix
        prefix = "/1.0"
        return ('<link rel="%(rel)s" title="%(title)s" '
                'href="%(prefix)s/%(collection)s%(obj_id)s" />') % \
            {'rel': rel, 'title': title, 'prefix': prefix,
             'collection': self.collection, 'obj_id': obj_id}

    def _datetime_parser(self, dct):
        for k, v in dct.items():
            #TODO: update regex to match time better
            if isinstance(v, basestring) and re.search("\ UTC", v):
                try:
                    dct[k] = datetime.strptime(v, self.DATE_FORMAT)
                except:
                    # this is a normal string
                    pass
        return dct

    ######################################
    ## Preparing response into proper mime
    def _prep_response(self, dct=None, last_modified=None, etag=None,
                       status=200, **kwargs):
        # TODO: handle more mime types
        mime = "application/json"
        rendered = "" if dct is None else json_util.dumps(dct)
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
        resp.mimetype = mime
        return resp

    def _validation_response(self, obj):
        response = {}
        for k, v in obj.validation_errors.iteritems():
            key = "structure" if k is None else k
            response[key] = []
            for error in v:
                response[key].append(error.message)
        return Response(json_util.dumps(response), 400)

    def authorized(self, **kwargs):
        if g.user.get('is_superuser', False) or \
                g.user.get('is_site_manager', False):
            return True
        has_perms = False
        perm = {'GET': "view", 'POST': "add", 'PATCH': "change",
                'DELETE': "delete"}

        for group in g.user.get('groups', []):
            if "%s_%s" % (perm[request.method], self.collection[:-1]) in \
                    group.get('permissions', []):
                has_perms = True
                break
        return has_perms

    def limit_fields(self, data, **kwargs):
        """ Limit the fields returned in the response"""
        return data

    def _auth_limits(self, **kwargs):
        """ Generates mandatory arguments which limit the objects by
        user permissions """

        args = {} if kwargs.get('is_instance', False) else {'spec': {}}
        if request.method == "GET":
            if 'lookup' in kwargs:
                args.update({self.lookup_field: kwargs.get('lookup')})
            elif 'obj_id' in kwargs:
                args.update({'_id': ObjectId(kwargs.get('obj_id'))})
            else:
                args['limit'] = int(request.args.get('limit', 25))
                args['skip'] = int(request.args.get('skip', 0))
                if 'where' in request.args:
                    args['spec'].update(json_util.loads(
                        request.args.get('where')))

        site_filter = {'site': g.site['_id']} if self.require_site_filter \
            or not g.user['is_superuser'] else {}
        if kwargs.get('is_instance', False):
            args.update(site_filter)
            if 'lookup' in kwargs:
                args[self.lookup_field] = kwargs.get('lookup')
            else:
                args['_id'] = kwargs.get('obj_id', "")
        else:
            args['spec'].update(site_filter) if 'spec' in args else \
                args.update(site_filter)

        # Adding custom auth limits to the arguments
        custom_limits = self.custom_auth_limits(**kwargs)
        current_app.logger.debug("Custom limits: %s" % custom_limits)
        if custom_limits is None:
            abort(404)

        # ensure we can never pass the site variable in throug the url
        if 'site' in custom_limits:
            del custom_limits['site']

        args.update(custom_limits) if kwargs.get('is_instance', False) else \
            args['spec'].update(custom_limits)
        current_app.logger.debug("Query Args: %s" % args)
        return args

    def _pre_validate(self, data, **kwargs):
        """ System pre-validate to prevent overwriting id"""
        if '_id' in data:
            del data['_id']
        return self.pre_validate(data, **kwargs)

    def pre_validate(self, data, **kwargs):
        """ Hook for changing the data before it gets validated on a POST
        request. Useful if additional keys need to be added to the data
        which the user shouldn't not have access to."""
        return data

    def _get_projection(self):
        projection = None
        if '_fields' in request.args:
            projection = {}
            for k in request.args.getlist('_fields'):
                projection[k] = 1
        return projection

    def _get_collection(self):
        current_app.logger.debug("GETting collection")
        documents = []
        try:
            query = {} if g.access_limits is None else g.access_limits
            cursor = current_app.db[self.collection] \
                .find(query, self._get_projection())
            if 'sort' in request.args:
                sort = []
                for k, v in json_util.loads(request.args['sort']).iteritems():
                    sort.append(
                        (k, pymongo.ASCENDING if v else pymongo.DESCENDING))
                cursor = cursor.sort(sort)
            for document in cursor:
                document['id'] = str(document.pop('_id'))
                documents.append(document)
        except ValueError:
            abort(400)

        return {self.collection: documents}

    def _get_instance(self, **kwargs):
        current_app.logger.debug("GETting instance")

        if 'obj_id' in kwargs:
            query = {'_id': ObjectId(kwargs['obj_id'])}
        else:
            query = {self.lookup_field: kwargs['lookup']}
        count = current_app.db[self.collection].find(query).count()
        if count < 1:
            raise ApiException("No record found for this lookup")
        elif count > 1:
            raise ApiException("Multiple records found for this lookup")

        #TODO: add field limits into query so we can use indexes if available
        doc = current_app.db[self.collection].find_one(
            query, self._get_projection())
        return {self.collection: doc}

    def get_links(self, response, args, **kwargs):
        """ Adding generic links to the end of the queryset to satisfy the
        HATEOAS requirement of a RESTful interface """
        links = []
        if request.method == "GET":
            if kwargs.get('is_instance', False):
                perms = set(['add_user', 'change_user', 'delete_user',
                             'view_user'])

                add_link = False
                for group in g.user.get('groups', []):
                    if len(perms.intersection(
                            set(group.get('permissions', [])))) < 1:
                        continue
                    add_link = True
                if not add_link and not g.user.get('is_superuser', False):
                    return links
                links.append(self._link("collection"))
            else:
                params = urlencode(request.args)
                params = "" if params.strip() == "" else "?%s" % params
                links.append(self._link("self", obj_id=params))
                if args['skip'] > 0:
                    # add previous link
                    params = args.copy()
                    params['skip'] = max(0, args['skip'] - args['limit'])
                    links.append(self._link(
                        "previous", title="Previous %s" % self.collection,
                        obj_id="?%s" % urlencode(params)))
                if len(response[self.collection]) == args['limit']:
                    # add next link
                    params = args.copy()
                    params['skip'] = args['skip'] + args['limit']
                    links.append(self._link(
                        "next", title="Next %s" % self.collection,
                        obj_id="?%s" % urlencode(params)))
        return links

    @preflight_checks
    def delete(self, **kwargs):
        kwargs['is_instance'] = True

        try:
            obj = self._get_instance(**kwargs)[self.collection]
            current_app.db[self.collection].remove(obj['_id'])
            return self._prep_response(status=204)
        except ApiException, e:
            if e.message.find('No record') == 0:
                return self._prep_response(status=404)
            else:
                return self._prep_response(status=409)

    @preflight_checks
    def get(self, **kwargs):
        """ GET request entry point. We split the request into 2 paths:
            Getting a specific instance, either by id or lookup field
            Getting a list of records"""
        current_app.logger.debug("kwargs: %s" % kwargs)
        if 'lookup' in kwargs or 'obj_id' in kwargs:
            kwargs['is_instance'] = True
        if 'is_instance' in kwargs:
            try:
                response = self._get_instance(**kwargs)
            except ApiException, e:
                if e.message.find('No record') == 0:
                    return self._prep_response(status=404)
                else:
                    return self._prep_response(status=409)
        else:
            response = self._get_collection()

        return self._prep_response(response)

    @preflight_checks
    def patch(self, **kwargs):
        try:
            data = self._get_instance(**kwargs)[self.collection]
            current_app.logger.debug("Obj pre change: %s" % data)
            change = {} if request.data.strip() == "" else \
                request.json.copy()[self.collection]

            change = self.validation.pre_validation_transform(change)
            final = data.copy()
            final.update(change)
            self.validation.validate(final)
            if len(self.validation.errors) > 0:
                return self._prep_response(self.validation.errors, status=400)
            current_app.db[self.collection].update(
                {"_id": data['_id']}, {"$set": change})
            return self._prep_response({self.collection: final}, status=202)
        except ApiException, e:
            if e.message.find('No record') == 0:
                return self._prep_response(status=404)
            else:
                return self._prep_response(status=409)
        except Exception, e:
            current_app.logger.warning("Validation Failed: %s" % e.message)
            return self._prep_response(e.message, status=400)

    @preflight_checks
    def post(self):
        data = {} if request.data.strip() == "" else \
            request.json.copy()
        if self.collection not in data:
            return self._prep_response("No collection in payload",
                                       status=400)
        data = data[self.collection]

#        if self.require_site_filter or not g.user['is_superuser']:
#            data['site'] = g.user['site']
#        data = self._pre_validate(data)

#        obj = self.model(data)
        try:
            data = self.validation.pre_validation_transform(data)
            self.validation.validate(data)
#            obj.validate()
            if len(self.validation.errors) > 0:
                return self._prep_response(self.validation.errors, status=400)
            obj_id = current_app.db[self.collection].insert(data)
#            links = []
#            links.append(self._link('self', obj_id=obj_id))
#            links.append(self._link('collection'))
            #TODO: figure out prefix
#            location = '1.0/%s/%s' % (self.collection, obj_id)
            location = '%s/%s' % (self.collection, obj_id)
#            return self._prep_response({'links': links}, status=201)
            return self._prep_response(status=201,
                                       headers=[('Location', location)])
        except ApiException, e:
            current_app.logger.warning("Validation Failed: %s" % e.message)
            return self._prep_response(e.message, status=400)

    @preflight_checks
    def put(self, **kwargs):
        try:
            obj = self._get_instance(**kwargs)[self.collection]
            new_obj = {} if request.data.strip() == "" else \
                request.json.copy()[self.collection]

            new_obj = self.validation.pre_validation_transform(new_obj)
            self.validation.validate(new_obj)
            if len(self.validation.errors) > 0:
                return self._prep_response(self.validation.errors, status=400)
            query = {'$set': new_obj, '$unset': {}}

            # Remove all fields not included in PUT request
            for k in obj.keys():
                if k not in new_obj and k != '_id':
                    query['$unset'][k] = 1

            current_app.db[self.collection].update(
                {"_id": obj['_id']}, query)
            new_obj['_id'] = obj['_id']
            return self._prep_response({self.collection: new_obj}, status=202)
        except ApiException, e:
            if e.message.find('No record') == 0:
                return self._prep_response(status=404)
            else:
                return self._prep_response(status=409)
        except Exception, e:
            current_app.logger.warning("Validation Failed: %s" % e.message)
            return self._prep_response(e.message, status=400)

    def options(self, **kwargs):
        return NotImplementedError()


class ValidationDocument(Document):
    raise_validation_errors = False
    skip_validation = False
    use_dot_notation = True
    use_schemaless = True

    def validate(self):
        super(ValidationDocument, self).validate()
        # ensure required fields are set with some value
        for k in self.required_fields:
            if type(self.get(k)) not in [unicode, str]:
                continue
            if k in self and self.get(k).strip() == "":
                self._raise_exception(
                    RequireFieldError, k, "%s cannot be empty" % k)

    def __getattribute__(self, key):
        # overrite this since we don't use the db or connection for validation
        return super(Document, self).__getattribute__(key)

    def _get_size_limit(self):
        # no connection to the db, so we assume the latest size (mongo 1.8)
        return (15999999, '16MB')