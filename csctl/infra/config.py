from dynaconf import Dynaconf

settings = Dynaconf(envvar_prefix=False)


class Config:
    PATH_INITD = '/etc/init.d'
    PATH_SBIN = '/usr/sbin'
    PATH_PID = '/var/run/cs'
    PATH_CORTEX = '/usr/local/bin/cs_legacy/cortex'
    PATH_SCRIPT = 'scripts'
    PREFIX = 'cs'
    TEMPLATE = 'csinit'
    RENDER = 'render'
    BRAIN = 'brain'
    DB_NAME = '__prime__'
    COLLECTION = 'devops'
    HTTP_DEFAULT_PORT = 6480
    MONGODB_URL = settings.MONGODB_URL

