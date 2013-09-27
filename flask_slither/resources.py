# -*- coding: utf-8 -*-
from __future__ import with_statement

#from api.decorators import authenticate
from bson.objectid import ObjectId
from bson import json_util
from datetime import datetime
from flask import current_app, abort, request, make_response, g, redirect
from flask.views import MethodView
from flask.ext.slither.authentication import NoAuthentication
from flask.ext.slither.authorization import NoAuthorization
from flask.ext.slither.exceptions import ApiException
from flask.ext.slither.validation import NoValidation
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
        if request.method not in self.allowed_methods:
            return self._prep_response("Method Unavailable", status=405)

        current_app.logger.debug("%s request received" %
                                 request.method.upper())
        if not self.authentication.is_authenticated():
            msg = g.authentication_error \
                if hasattr(g, 'authentication_error') else None
            current_app.logger.warning("Unauthenticated request")
            return self._prep_response(msg, status=401)
        if not self.authorization.is_authorized(
                model=self.model, collection=self.collection):
            current_app.logger.warning("Unauthorized request")
            msg = g.authorization_error \
                if hasattr(g, 'authorization_error') else None
            return self._prep_response(msg, status=403)
        if self.collection is None:
            return self._prep_response("No collection defined",
                                       status=424)
        if request.method in ['POST', 'PUT', 'PATCH']:
            # enforcing collection as root of payload
            g.data = {} if request.data.strip() == "" else \
                json_util.loads(request.data)
            if self._get_root() not in g.data:
                if self.enforce_payload_collection:
                    return self._prep_response("No collection in payload",
                                               status=400)
            else:
                g.data = g.data[self._get_root()]

        return f(self, *args, **kwargs)
    return decorator


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
        if hasattr(self, 'redirect'):
            return redirect(self.redirect)
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

    def limit_fields(self, **kwargs):
        """A set of fields used mongo query. Fields can be passed in the
        query, but listing them here sets fields up as default. Useful if
        you want a subset of fields for an object every time except in
        unusual circumstances, eg {'password': 0}"""
        return {}

    def access_limits(self, **kwargs):
        """ Returns a query which filters the current collection based on
        authentication access"""
        return {}

    def pre_validation_transform(self, data, **kwargs):
        """ Transform the data by adding or removing fields before the
        data is validated. Useful for adding server generated fields, such
        as an author for a post. We assume that all fields are mongo references
        since mostly they will be"""
        for k, v in data.iteritems():
            if isinstance(v, dict) and '$oid' in v:
                data[k] = ObjectId(v['$oid'])
        for k, v in kwargs.iteritems():
            if k == '_lookup':
                continue
            data[k] = ObjectId(v)
        return data

    def post_save(self, **kwargs):
        """ A hook to run other code that depends on successful post"""
        pass

    def delete_query(self, **kwargs):
        obj = self._get_instance(**kwargs)[self._get_root()]
        return obj['_id']

    def _get_projection(self):
        projection = {}
        if '_fields' in request.args:
            projection = {}
            for k in request.args.getlist('_fields'):
                projection[k] = 1
        final = self.limit_fields()
        final.update(projection)
        return None if final == {} else final

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
            for document in cursor:
                document['id'] = str(document.pop('_id'))
                documents.append(document)
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
            # return 404 if instance not in access_limits
            k = query.keys()[0]
            vals = al[k] if isinstance(al[k], list) else [al[k]]
            if query[k] not in vals:
                    query[k] = False  # Ensure no matching element
        else:
            query.update(self.access_limits(**kwargs))

        count = current_app.db[self.collection].find(query).count()
        if count < 1:
            raise ApiException("No record found for this lookup")
        elif count > 1:
            raise ApiException("Multiple records found for this lookup")

        #TODO: add field limits into query so we can use indexes if available
        doc = current_app.db[self.collection].find_one(
            query, self._get_projection())
        return {self._get_root(): doc}

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
        return '%s/%s' % (location, obj_id)

    @preflight_checks
    def delete(self, **kwargs):
        kwargs['is_instance'] = True

        try:
            current_app.db[self.collection].remove(self.delete_query(**kwargs))
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
        if '_lookup' in kwargs or 'obj_id' in kwargs:
            kwargs['is_instance'] = True
        if 'is_instance' in kwargs:
            try:
                response = self._get_instance(**kwargs)
            except ApiException, e:
                if isinstance(e.message, dict):
                    return self._prep_response(
                        e.message['msg'], status=e.message['status'])
                if e.message.find('No record') == 0:
                    return self._prep_response(status=404)
                else:
                    return self._prep_response(status=409)
        else:
            response = self._get_collection(**kwargs)

        return self._prep_response(response)

    @preflight_checks
    def patch(self, **kwargs):
        try:
            data = self._get_instance(**kwargs)[self._get_root()]
            current_app.logger.debug("Obj pre change: %s" % data)
            change = self.pre_validation_transform(g.data, **kwargs)
            final = data.copy()
            final.update(change)
            self.validation.validate(final, model=self.model,
                                     collection=self.collection)
            if len(self.validation.errors) > 0:
                return self._prep_response(self.validation.errors, status=400)
            current_app.db[self.collection].update(
                {"_id": data['_id']}, {"$set": change})
            self.post_save(collection=self.collection, data=data,
                           change=change)
            return self._prep_response(status=204)
        except ApiException, e:
            if e.message.find('No record') == 0:
                return self._prep_response(status=404)
            else:
                return self._prep_response(status=409)
        except Exception, e:
            current_app.logger.warning("Validation Failed: %s" % e.message)
            return self._prep_response(e.message, status=400)

    @preflight_checks
    def post(self, **kwargs):
        try:
            data = self.pre_validation_transform(g.data, **kwargs)
            self.validation.validate(data, model=self.model,
                                     collection=self.collection)
            if len(self.validation.errors) > 0:
                return self._prep_response(self.validation.errors, status=400)
            is_update = '_id' in data
            obj_id = current_app.db[self.collection].save(data)

            self.post_save(collection=self.collection, data=data)
            location = self.get_location(obj_id, **kwargs)
            if is_update:
                return self._prep_response()
            return self._prep_response(status=201,
                                       headers=[('Location', location)])
        except ApiException, e:
            current_app.logger.warning("Validation Failed: %s" % e.message)
            return self._prep_response(e.message, status=400)

    @preflight_checks
    def put(self, **kwargs):
        try:
            obj = self._get_instance(**kwargs)[self._get_root()]

            new_obj = self.pre_validation_transform(g.data, **kwargs)
            self.validation.validate(new_obj, model=self.model,
                                     collection=self.collection)
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
            self.post_save(collection=self.collection, data=new_obj)
            return self._prep_response(status=204)
        except ApiException, e:
            if e.message.find('No record') == 0:
                return self._prep_response(status=404)
            else:
                return self._prep_response(status=409)
        except Exception, e:
            current_app.logger.warning("Validation Failed: %s" % e.message)
            return self._prep_response(e.message, status=400)

    def options(self, **kwargs):
        """This method has been left open for fine grain control in the
        application (for security reasons)."""
        return NotImplementedError()
