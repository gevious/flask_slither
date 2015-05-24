"""
    flaskext.slithers
    ~~~~~~~~~~~~~~~~~

    Flask extension for quickly building RESTful API. Based on flask-slither,
    but is now somewhat more database agnostic and has an improved workflow.

    :copyright: (c) 2015 by Nico Gevers.
    :license: MIT, see LICENSE for more details.
"""
import inflect

__author__ = 'Nico Gevers'
__version__ = (1, 1, 1)


def register_resource(mod, view, **kwargs):
    """Register the resource on the resource name or a custom url"""
    resource_name = view.__name__.lower()[:-8]
    endpoint = kwargs.get('endpoint', "{}_api".format(resource_name))
    plural_resource_name = inflect.engine().plural(resource_name)
    path = kwargs.get('url', plural_resource_name).strip('/')
    url = '/{}'.format(path)
    setattr(view, '_url', url)  # need this for 201 location header
    view_func = view.as_view(endpoint)

    mod.add_url_rule(url, view_func=view_func,
                     methods=['GET', 'POST', 'OPTIONS'])
    mod.add_url_rule('{}/<obj_id>'.format(url),
                     view_func=view_func,
                     methods=['GET', 'PATCH', 'PUT', 'DELETE', 'OPTIONS'])


class ApiException(Exception):
    def __init__(self, message, status):
        self.message = message
        self.status = status
        Exception.__init__(
            self, "API Exception: {}, {}".format(status, message))
