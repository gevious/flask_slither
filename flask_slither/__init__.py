__author__ = 'Nico Gevers'
__version__ = (0, 0, 1, 'dev')

from werkzeug.routing import BaseConverter


class RegexConverter(BaseConverter):
    def __init__(self, url_map, *items):
        super(RegexConverter, self).__init__(url_map)
        self.regex = items[0]


def register_api(mod, view, **kwargs):
    name = view.__name__[:-3].lower()
    endpoint = kwargs.get('endpoint', "%s_api" % name)
    url = "/%s" % kwargs.get('url', "%ss" % name)
    view_func = view.as_view(endpoint)

    mod.url_map.converters['regex'] = RegexConverter

    mod.add_url_rule("%s" % url, view_func=view_func,
                     methods=['GET', 'POST', 'OPTIONS'])
    mod.add_url_rule('%s/<regex("[a-f0-9]{24}"):obj_id>' % url,
                     view_func=view_func,
                     methods=['GET', 'PATCH', 'DELETE', 'OPTIONS'])
    mod.add_url_rule('%s/<lookup>' % url,
                     view_func=view_func,
                     methods=['GET', 'PATCH', 'DELETE', 'OPTIONS'])
