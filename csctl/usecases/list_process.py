from typing import Dict


class ListProcessUseCase:
    def __init__(self, process_repo):
        self.process_repo = process_repo

    def list_process(self) -> Dict:
        return self.process_repo.list_process()


