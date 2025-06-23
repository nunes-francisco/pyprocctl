from infra.config_mongodb import MongoConnect
from infra.config_mongodb import FailureOperation
from infra.config import Config


settings = Config()


class MongoRepo:
    def __init__(self, db=None, collection=None, url=None):
        self.mongodb_url = url
        self.db = db
        self.collection = collection
        self.cursor = MongoConnect(self.mongodb_url).connect()

    def _create_services_object(self, services_object):
        """ Insere documentos no mongodb"""
        try:
            self.cursor[self.db][self.collection].insert_one(services_object)
        except FailureOperation as err:
            raise err
        return

    def update_services_object(self, object_one, object_two):
        """ Atualiza um documento existente com novos serviços"""
        try:
            self.cursor[self.db][self.collection].update_one(object_one, object_two)
        except FailureOperation as err:
            raise err
        return

    def find_all_services_object(self, one_object, two_object=None):
        """ Pesquisa documentos no mongodb"""
        try:
            documents = self.cursor[self.db][self.collection].find(one_object, two_object)
        except FailureOperation as err:
            raise err
        return documents

    def _remove_services_object(self, services_object):
        """ Remove documentos no mongodb"""
        try:
            self.cursor[self.db][self.collection].delete_many(services_object)
        except FailureOperation as err:
            raise err
        return
