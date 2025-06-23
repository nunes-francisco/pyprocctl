from typing import List


class ListDirUseCase:
    def __init__(self, dir_repo):
        self.dir_repo = dir_repo
        self.list_dirs = dir_repo.list_dirs

    def list_dir(self) -> List:
        return self.list_dirs
