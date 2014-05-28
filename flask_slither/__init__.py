"""
    flaskext.slither
    ~~~~~~~~~~~~~~~~

    Flask extension for quickly building RESTful API resources from MongoDB.

    :copyright: (c) 2013 by Nico Gevers.
    :license: MIT, see LICENSE for more details.
"""

__author__ = 'Nico Gevers'
__version__ = (0, 4, 21)


def _pluralize(name):
    if name.strip() == "":
        return name

    if name[-1] == 'y':
        name = "%sie" % name[:-1]
    return "%ss" % name


def register_api(mod, view, **kwargs):
    name = view.__name__.lower()[:-8]  # remove _api from the end
    endpoint = kwargs.get('endpoint', "%s_api" % name)
    path = kwargs.get('url', _pluralize(name)).strip('/')
    url = '/{}'.format(path)
    setattr(view, '_url', url)  # need this for 201 location header
    view_func = view.as_view(endpoint)

    mod.add_url_rule("%s" % url, view_func=view_func,
                     methods=['GET', 'POST', 'OPTIONS'])
    mod.add_url_rule('%s/<regex("[a-f0-9]{24}"):obj_id>' % url,
                     view_func=view_func,
                     methods=['GET', 'PATCH', 'PUT', 'DELETE', 'OPTIONS'])
    mod.add_url_rule('%s/<_lookup>' % url,
                     view_func=view_func,
                     methods=['GET', 'PATCH', 'PUT', 'DELETE', 'OPTIONS'])
    # TODO: add hook to add custom routes that user provides
    # TODO: add regex url mapper somewhere here that works for blueprints
    #      and where mod=app
