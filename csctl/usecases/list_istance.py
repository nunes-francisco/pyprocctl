from typing import Dict


class ListInstanceUseCase:
    def __init__(self, service_repo):
        self.service_repo = service_repo

    def list_instances(self, object_one, object_two) -> Dict:
        """ Retorna um dicionário com as instâncias registardas"""
        return self.service_repo.find_all_services_object(object_one, object_two)


class UpdateInstanceUseCase:
    def __init__(self, service_repo):
        self.service_repo = service_repo

    def update_instances(self, object_one, object_two) -> Dict:
        """ Executa cursor para atualizar serviços"""
        return self.service_repo.update_services_object(object_one, object_two)
