.. _ref-tutorial:

============================
Getting Started with Slither
============================
Flask-Slither allows you to sublass a `resource` which provides the entry point
for all http methods (GET, POST, PUT, PATCH, DELETE, OPTION).  A resource and
URI are fairly synonymous. Ie goign to the url `/foo` will provide the Foo
object while goign to the url `/bar` gives you access to the bar object. These
need map to a MongoDB collection by default (foos and bars respectively)

.. note::

    Currently there is no mailing list for slither, so please create an issue
    on slither's `github repo`_ to get help.

.. _github repo: http://github.com/gevious/flask_slither

A good knowledge of Flask is useful, but not necessary. At least a basic
knowledge of Flask is beneficial, even though this tutorial will cater for the
absolute beginner.

This tutorial will walk you through the creating of a simple library
application.  By the end of this tutorial you will know how to CRUD books in
the library as well lend out and return books.

Installation
============

Make sure you have at least Python 2.5+ installed, along with virtualenv.

It is always a good idea to run any project in a virtualenv. First setup the
virtualenv for your project then load the needed dependencies.::

    $ virtualenv --no-site-packages library
    $ cd library
    ~/library $ source ./bin/activate
    ~/library $ pip install Flask-Slither

All dependencies needed for Flask-Slither will be installed, so there is no
need to explicitly install Flask first. The output will reveal that Flask is,
in fact, installed as well.

.. note::
  The dateutil, pytz and blinker libraries are installed by default and are
  used by some of the authentication module. If you're running a lean system
  and don't want the overhead, you can override the modules that need the
  libraries and remove them from your virtualenv.

To make sure that your install was successful open a python prompt and type
the following::

    >>> from flask.ext.slither import register_api
    >>>


Creating the App
================

We'll be creating a very simple Flask app.  First we create a directory for
our application and then edit the `__init__.py` file using our favourite editor::

    $ mkdir app
    $ vi __init__.py

Next we create a basic Flask application (in `app/__init__.py`).

.. code-block:: python

    # -*- coding: utf-8 -*-
    from flask import Flask
    from pymongo import MongoClient
    from flask.ext.slither.resources import BaseResource
    from flask.ext.slither import register_api
    from werkzeug.routing import BaseConverter

    app = Flask(__name__)

    class RegexConverter(BaseConverter):
        def __init__(self, url_map, *items):
            super(RegexConverter, self).__init__(url_map)
            self.regex = items[0]

    app.url_map.converters['regex'] = RegexConverter

    # setup the connection to our mongo database
    app.config['DB_HOST'] = 'localhost'
    app.config['DB_PORT'] = 27017
    app.config['DB_NAME'] = 'library'
    client = MongoClient(app.config['DB_HOST'], app.config['DB_PORT'])
    app.db = client['app.config['DB_NAME']]

    if __name__ == "__main__":
       app.run(debug=True)

To check that we're on the right track, run the application by issuing the 
following command::

    ~/library $ cd app
    ~/library $ python __init__.py
     * Running on http://127.0.0.1:5000/
     * Restarting with reloader

.. note::
  If the server doesn't come up, ensure that you have mongodb installed and
  that it is up and running.

.. note::
  One caveat currently is installing the `RegexConverter`. This isn't strictly
  needed but is a useful addition. It allows us to reference a resource not
  just by its unique mongo id, but also by a field. By default it is the name
  field, but can be set per resource.

Creating the Resources
======================

Now that we know our setup is good, lets create the resources. We want our API
to support the following functions:

* Create a book with a name, ISBN number and quantity available
* Edit the details of a book
* Delete a book
* Get a list of all the books
* Check a book out of the library
* Return a book

These functions can be split into two logical sections. The first four items
will be covered by the *book* resource, and the last two by the *lending*
resource. The first resource maps explicitly to the MonboDB books collection.
For simplicity's sake, we'll map the lending resource to the books collection
as well, so that we can easily manipulate the data. In real life, we'd probably
want to track who has books, but for now we're keeping it simple. To start
with, lets create our two resources (in `__init__.py`).

.. code-block:: python

    ...
    app.url_map.converters['regex'] = RegexConverter

    class BookResource(BaseResource):
        collection = 'books'

    class LendingResource(BaseResource):
        collection = 'books'


    register_api(app, BookResource)
    register_api(app, LendingResource)

    if __name__ == "__main__":
        app.run(debug=True)


As you can see the definition is pretty simple. Firstly we subclass Slither's
BaseResource, and then we register the endpoints for the resource. As you
probably noticed, except for the endpoint name, accessing both these resources
will yield the same result.  That's because they reference the same MongoDB
collection. We'll change the `LendingResource` later.

Lets test this out. Start up your server and run the following cURL_ request
from the command line.::

  $ curl http://127.0.0.1:5000/books
  {"books": []}

.. _cURL: http://curl.haxx.se/

Ah, its working. But we have no books in the library just yet. Lets add one::

  $ curl --dump-header - -H "Content-Type: application/json" -X POST --data '{"books": {"name": "Python Cookbook, 3rd Edition", "quantity": 8, "isbn":"978-1449340377"}}' http://127.0.0.1:5000/books
  HTTP/1.0 201 CREATED
  Content-Type: application/json
  Content-Length: 0
  Cache-Control: max-age=30,must-revalidate
  Access-Control-Allow-Origin: *
  Location: http://127.0.0.1:5000/books/51a8feb6421aa965ffaf1435
  Expires: Fri, 31 May 2013 19:51:30 GMT
  Server: Werkzeug/0.8.3 Python/2.7.3
  Date: Fri, 31 May 2013 19:51:00 GMT


You'll see from the responses that each of the books was created successfully.
Notice that the header also returned the URI of the book. We should be able
to access that book from the link::

  $ curl http://127.0.0.1:5000/books/51a8feb6421aa965ffaf1435
  {"books": {"_id": {"$oid": "51a8feb6421aa965ffaf1435"}, "ISBN": "978-1449340377", "name": "Python Cookbook, 3rd Edition", "quantity": 8}

  $ curl http://127.0.0.1:5000/books
  {"books": [{"_id": {"$oid": "51a8feb6421aa965ffaf1435"}, "ISBN": "978-1449340377", "name": "Python Cookbook, 3rd Edition", "quantity": 8}]

.. note::
  The actual location of the book will differ on your setup, so copying of the
  cURL command verbatim will not work. Rather copy it from the location header.
