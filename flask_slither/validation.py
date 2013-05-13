class NoValidation():
    """No validation is done and no errors are returned"""
    errors = {}

    def pre_validation_transform(self, data):
        return data

    def validate(self, data):
        pass
