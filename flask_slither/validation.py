#from mongokit.schema_document import RequireFieldError
#from mongokit.document import Document


class NoValidation():
    """No validation is done and no errors are returned"""
    errors = {}

    def validate(self, data, **kwargs):
        pass


class Validation():
    errors = {}

    def validate(self, data, **kwargs):
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


#class ValidationDocument(Document):
#    """Object validation using MongoKit"""
#    raise_validation_errors = False
#    skip_validation = False
#    use_dot_notation = True
#    use_schemaless = True
#
#    def validate(self):
#        super(ValidationDocument, self).validate()
#        # ensure required fields are set with some value
#        for k in self.required_fields:
#            if type(self.get(k)) not in [unicode, str]:
#                continue
#            if k in self and self.get(k).strip() == "":
#                self._raise_exception(
#                    RequireFieldError, k, "%s cannot be empty" % k)
#
#    def __getattribute__(self, key):
#        # overrite this since we don't use the db or connection for validation
#        return super(Document, self).__getattribute__(key)
#
#    def _get_size_limit(self):
#        # no connection to the db, so we assume the latest size (mongo 1.8)
#        return (15999999, '16MB')
