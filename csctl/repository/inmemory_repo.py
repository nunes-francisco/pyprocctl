from abc import ABC, abstractmethod
from collections.abc import MutableMapping
from glob import glob
import os
import psutil
import re
import time


class InMemoryProcessRepo(ABC):
    def __init__(self, filters):
        self.filters = filters

    @property
    @abstractmethod
    def filters(self):
        pass

    @filters.setter
    @abstractmethod
    def filters(self, value):
        pass

    @abstractmethod
    def list_process(self):
        pass


class InMemoryFieldsRepo(ABC):
    def __init__(self, fields):
        self.fields = fields

    @property
    @abstractmethod
    def fields(self):
        pass

    @fields.setter
    @abstractmethod
    def fields(self, value):
        pass


class InMemoryRepo(ABC):
    def __init__(self, file_name=None, path_name=None):
        self.script_service = file_name
        self.path_name = path_name

    @property
    @abstractmethod
    def list_files(self, file_name, path_name):
        pass

    @list_files.setter
    @abstractmethod
    def list_files(self, values):
        pass


class InMemoryDirRepo(ABC):
    def __init__(self, path_name=None):
        self.path_name = path_name

    @property
    @abstractmethod
    def list_dirs(self, path_name):
        pass

    @list_dirs.setter
    @abstractmethod
    def list_dirs(self, values):
        pass


class ListDirRepo(InMemoryDirRepo):
    def __init__(self, path_name=None):
        self.__path_name = path_name

    @property
    def list_dirs(self):
        return os.listdir(self.__path_name)

    @list_dirs.setter
    def list_dirs(self, values):
        self.__path_name


class ListFilesRepo(InMemoryRepo):
    def __init__(self, file_name=None, path_name=None):
        self.__file_name = file_name
        self.__path_name = path_name
        self.__object_path = os.path.join(self.__path_name, self.__file_name)
        self.__object_glob = glob('{}/cs*'.format(self.__path_name))

    @property
    def list_files(self):
        for script in self.__object_glob:
            if self.__file_name:
                real_path = self.__object_path
                if script.startswith(real_path):
                    yield script
                else:
                    yield script

    @list_files.setter
    def list_files(self, path_name, file_name):
        self.__path_name = path_name
        self.__file_name = file_name


class ListProcessRepo(InMemoryProcessRepo):
    def __init__(self, filters):
        self.__filters = filters
        self.__version = 'python3'
        self.__process_name = None
        self.__process_pid = None
        self.__process_started = None
        self.__process_memory = None
        self.__process_cpu = None
        self.__selected_process = None
        self.__parameters = None
        self.__arguments = None
        self.__environ = None
        self.__connections = None

    @property
    def filters(self):
        return self.__filters

    @filters.setter
    def filters(self, value):
        self.__filters = value

    def list_process(self):
        for proc in psutil.process_iter(attrs=self.filters):
            if proc.info[self.filters[0]].startswith(self.__version):
                self.__process_name = list(filter(lambda v: re.match('^(cs[a-z].*)', v), proc.info[self.filters[6]]))
                self.__process_pid = proc.info[self.filters[2]]
                self.__process_started = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(proc.info[self.filters[1]]))
                self.__process_memory = round(proc.info[self.filters[4]])
                self.__process_cpu = round(proc.info[self.filters[3]])
                self.__parameters = list(filter(lambda v: re.match('^(--[a-z].*)', v), proc.info['cmdline']))
                self.__arguments = list(filter(lambda v: re.match('^([^\-\-])', v), proc.info['cmdline']))
                self.__environ = proc.info['environ']
                self.__connections = proc.info['connections']
                if (0 <= 0 < len(self.__process_name)) or (-len(self.__process_name) <= 0 < 0):
                    self.__selected_process = {'name': self.__process_name[0],
                                            'pid': self.__process_pid,
                                            'started': self.__process_started,
                                            'memory_percent': self.__process_memory,
                                            'cpu_percent': self.__process_cpu,
                                            'parameters': self.__parameters,
                                            'environ': self.__environ,
                                            'connections': self.__connections,
                                            'arguments': self.__arguments}

                yield self.__selected_process


class ListFieldsRepo(InMemoryFieldsRepo):
    def __init__(self):
        self.__fields = ["name", 'create_time', "pid", 'cpu_percent', 'memory_percent', "status", "cmdline", "environ",
                         "connections"]

    @property
    def fields(self):
        return self.__fields

    @fields.setter
    def fields(self, value):
        self.__fields = value


class DitcInstanceRepo(MutableMapping):
    def __init__(self, *args, **kwargs) -> None:
        self.__dict__.update(*args, **kwargs)

    def __setitem__(self, key, value):
        self.__dict__[key] = value

    def __getitem__(self, key):
        return self.__dict__[key]

    def __delitem__(self, key):
        del self.__dict__[key]

    def __iter__(self):
        return iter(self.__dict__)

    def __len__(self):
        return len(self.__dict__)

    # The final two methods aren't required, but nice for demo purposes:
    def __str__(self):
        """returns simple dict representation of the mapping"""
        return str(self.__dict__)

    def __repr__(self):
        """echoes class, id, & reproducible representation in the REPL"""
        return '{}, RepoDict({})'.format(super(DitcInstanceRepo, self).__repr__(), self.__dict__)


# mylist = ListFilesRepo('cs', '../scripts')
#
# for i in mylist.list_files:
#     if os.path.isfile(i):
#         print(f'file is - {os.path.basename(i)}')
#
# ld = ListDirRepo('../../../cortex')
#
# print(ld.list_dirs)
