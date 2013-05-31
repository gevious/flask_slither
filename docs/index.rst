.. Flask Slither documentation master file, created by
   sphinx-quickstart on Thu May 16 08:14:44 2013.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to Flask Slither
========================

Slither is an API 'framework' for Flask which interfaces with MongoDB.
It allows for rapid API development as well as customisations needed for
bigger projects.

.. toctree::
   :maxdepth: 2

   tutorial

Requirements
============
The following are base requirements for Slither to function out the box:

Required
--------
* Python 2.5+
* MongoDB
* Flask 0.9
* pymongo 2.5

Optional
--------
* mongokit (For form validations)
* Flask-Testing (to run the tests)
* nose (to execute the tests)
* pytz, python-dateutil, blinker (for signed request authentication)

Why Slither?
============
Building a RESTful application is nothing new. When using mongo as a backend,
the payload is in JSON, and if the API produces (mostly) JSON, then only a 
thin layer of logic is needed between the two. Here are some features:

* Uses Flask's ``MethodView`` as a basis for API endpoints
* Its fast because it uses pymongo directly with little overhead
* Quick and easy setup
* Optional validation avaliable using MongoKit's validation engine

Slither is based on Django's Tastypie, and uses constructs that will be
familiar tho developers who've used tastypie before.

Testing Slither
===============
The easiest way to run the unit tests, is to install nose and Flask-Testing.
Simply navigate to the root of the flask_slither code and run ``nosetests``
and the tests will run. Make sure you have a mongo instance up and running
otherwise the tests will fail.
