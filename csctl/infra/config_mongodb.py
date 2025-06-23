from pymongo import MongoClient, ReadPreference
from pymongo.errors import OperationFailure, CursorNotFound, ConnectionFailure


class FailureOperation(OperationFailure):
    """ Para exceptions de operaçoes"""


class ErrorCursor(CursorNotFound):
    """ Execptions com com cursores"""


class MetaSingleton(type):
    """ Metaclass que produzirar um padrão Singleton pocibilitando instanciar sempre o mesmo objeto
        gerando um ponto único reaproveitando a conexão.
    """

    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(MetaSingleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class MongoConnect(metaclass=MetaSingleton):
    """ Esta classe irá criar apenas um objeto de conexão e consulta sempre que for instanciada"""

    def __init__(self, url):
        self.cursorobj = None
        self.url = url

    connection = None

    def connect(self):
        if self.connection is None:
            try:
                self.connection = MongoClient(self.url, serverselectiontimeoutms=3000)
                self.cursorobj = self.connection
            except ConnectionFailure as err:
                raise err
        return self.cursorobj


