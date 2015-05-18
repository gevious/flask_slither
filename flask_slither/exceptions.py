class ApiException(Exception):
    def __init__(self, message):
        self.message = message
        Exception.__init__(
            self, "Message not found exception: missing {}".format(message))
