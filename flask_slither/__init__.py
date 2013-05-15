__author__ = 'Nico Gevers'
__version__ = (0, 0, 1, 'dev')


def register_api(mod, view, **kwargs):
    name = view.__name__.lower()[:-8]  # remove _api from the end
    endpoint = kwargs.get('endpoint', "%s_api" % name)
    url = "/%s" % kwargs.get('url', "%ss" % name)
    view_func = view.as_view(endpoint)

    mod.add_url_rule("%s" % url, view_func=view_func,
                     methods=['GET', 'POST', 'OPTIONS'])
    mod.add_url_rule('%s/<regex("[a-f0-9]{24}"):obj_id>' % url,
                     view_func=view_func,
                     methods=['GET', 'PATCH', 'PUT', 'DELETE', 'OPTIONS'])
    mod.add_url_rule('%s/<lookup>' % url,
                     view_func=view_func,
                     methods=['GET', 'PATCH', 'PUT', 'DELETE', 'OPTIONS'])
