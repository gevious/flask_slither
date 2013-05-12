flask_slither
=============

A small library to interface between a mongodb and JSON RESTful API endpoints.
It uses Flask's `MethodView` and populates it with boilerplate code. It is based
on django tastypie.

The idea behind Slither
=======================
MongoDB, or any document database, already has JSON payloads in the required
format. Not a lot of work needs to be done in de-normalising the data and 
building a JSON payload. Slither aims to be the small layer between the 
database and the API endpoint. It is there to do some housekeeping, but not to
get in the way.

Needed Libraries
================
 * Flask
 * pymongo
 * Mongokit (for its validation engine)

Usage
=====
Here are the basic code snippets you need to use to get up and running:

    from flask.ext.slither import BaseAPI, register_api, ValidationDocument

    class User(ValidationDocument):
    structure = {
      'name': unicode,
      'surname': unicode,
      'email': unicode
    }
    required_fields = ['name', 'email']


    class UserAPI(BaseAPI):
      def __init__(self, *args, **kwargs):
        self.collection = 'users'  # The db collection name
        self.model = User  # the model name, used for validation

    register_api(app, UserAPI)
