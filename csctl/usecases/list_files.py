from typing import List


class ListFileUseCase:
    def __init__(self, files_repo):
        self.files_repo = files_repo
        self.list_file = [f for f in self.files_repo.list_files]

    def list_files(self) -> List:
        return self.list_file
