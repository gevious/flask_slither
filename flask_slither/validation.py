from flask import g
from mongokit.schema_document import RequireFieldError
from mongokit.document import Document


class NoValidation():
    """No validation is done and no errors are returned"""
    errors = {}

    def pre_validation_transform(self, data):
        return data

    def validate(self, data, **kwargs):
        pass


class SiteNoValidation():
    """No actual validation, but adds site key to the payload"""
    errors = {}

    def pre_validation_transform(self, data):
        data['site'] = g.site['_id']
        return data

    def validate(self, data, **kwargs):
        pass


class SiteValidation():
    """Site pre_validation payload with mongokit validation"""
    errors = {}

    def pre_validation_transform(self, data):
        data['site'] = g.site['_id']
        return data

    def validate(self, data, **kwargs):
        self.errors = {}
        if 'model' not in kwargs:
            self.errors = {'__internal__': "No model defined for validation"}
            return
        obj = kwargs.get('model')(data)
        obj.validate()
        for k, v in obj.validation_errors.iteritems():
            key = "structure" if k is None else k
            self.errors[key] = []
            for error in v:
                self.errors[key].append(error.message)


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
