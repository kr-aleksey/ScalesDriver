import logging


class SerialError(Exception):
    def __init__(self, message=''):
        self.message = f'Serial error. {message}'
        logging.error(self.message)
        super().__init__(self.message)


class ScalesException(Exception):
    def __init__(self, message=''):
        self.message = f'Incorrect device response. {message}'
        logging.error(self.message)
        super().__init__(self.message)
