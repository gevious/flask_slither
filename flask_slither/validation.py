# -*- coding: utf-8 -*-
class NoValidation(object):
    """No validation is done and no errors are returned"""
    def __init__(self, *args, **kwargs):
        self.errors = {}


class Validation(NoValidation):
    def validate(self, data, **kwargs):
        self.errors = {}
        if 'model' not in kwargs:
            self.errors = {'__internal__': "No model defined for validation"}
            return
        obj = kwargs.get('model')(data)
        obj.validate()
        for k, v in obj.validation_errors.items():
            key = "structure" if k is None else k
            self.errors[key] = []
            for error in v:
                self.errors[key].append(error.message)

    def validate_post(self, **kwargs):
        self.validate(**kwargs)

    def validate_put(self, **kwargs):
        self.validate(**kwargs)

    def validate_patch(self, **kwargs):
        self.validate(**kwargs)
