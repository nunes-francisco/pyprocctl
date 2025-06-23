import logging
import os
import glob
import time
import click
import sys
import subprocess
import psutil
import signal
import shutil
import stat
import socket
import re
from jinja2 import Environment
from jinja2 import FileSystemLoader
from time import sleep
from prettytable import PrettyTable
from termcolor import colored
from prettytable import (SINGLE_BORDER, PLAIN_COLUMNS)

from repository.mongo_repo import MongoRepo
from repository.inmemory_repo import ListProcessRepo
from repository.inmemory_repo import ListFilesRepo
from repository.inmemory_repo import ListFieldsRepo
from repository.inmemory_repo import ListDirRepo
from repository.inmemory_repo import DitcInstanceRepo
from usecases.list_istance import ListInstanceUseCase
from usecases.list_process import ListProcessUseCase
from usecases.list_files import ListFileUseCase
from usecases.list_dirs import ListDirUseCase
from usecases.list_istance import UpdateInstanceUseCase
from infra.config import Config
from infra.config_hostname import IpAddrOrHostname

host_name = IpAddrOrHostname()
settings = Config()

# Crie um logger
logger = logging.getLogger("-")
logger.setLevel(logging.INFO)

# Crie um manipulador (por exemplo, saída para o console)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# Crie um formato para as mensagens de log
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)

# Adicione o manipulador ao logger
logger.addHandler(console_handler)

PATH_PID = settings.PATH_PID
PATH_INITD = settings.PATH_INITD
PATH_SBIN = settings.PATH_SBIN
PATH_CORTEX = settings.PATH_CORTEX
PATH_SCRIPT = os.path.join(os.path.abspath(os.path.dirname(sys.argv[0])), settings.PATH_SCRIPT)
TEMPLATE = settings.TEMPLATE
BRAIN = settings.BRAIN
RENDER = settings.RENDER
PREFIX = settings.PREFIX
HTTP_DEFAULT_PORT = settings.HTTP_DEFAULT_PORT
COLLECTION_NAME = settings.COLLECTION
DATABASE_NAME = settings.DB_NAME
CONFIG_DATABASE_URL = settings.MONGODB_URL

repo_fields = ListFieldsRepo()
repo_instance = MongoRepo(url=CONFIG_DATABASE_URL, db=DATABASE_NAME, collection=COLLECTION_NAME)
repo_process = ListProcessRepo(repo_fields.fields)
repo_files = ListFilesRepo(PREFIX, PATH_INITD)
repo_dirs = ListDirRepo(PATH_CORTEX)

use_case_files = ListFileUseCase(repo_files)
use_case_dirs = ListDirUseCase(repo_dirs)
use_case_process = ListProcessUseCase(repo_process)
use_case_instances = ListInstanceUseCase(repo_instance)
use_case_update = UpdateInstanceUseCase(repo_instance)

term_color = f"{colored('>', 'white')}{colored('>', 'green')}{colored('>', 'magenta')}"  # Pseudo terminal


def pretty_table(columns: str = None, fields: list = None, title: str = None):
    """ Formata o output das tabelas """
    table = PrettyTable()
    if title:
        table = PrettyTable(title=colored(title, 'magenta'))
    table.set_style(columns)
    table.field_names = fields
    table.align = "l"
    return table


def list_files():
    """ Retorna uma lista de arquivos"""
    services = []
    for f in use_case_files.list_files():
        service_name_file = f.split("/")[-1]
        services.append(service_name_file)
    return sorted(services)


def do_status(name_service=None):
    """ Retorna o estatus dos processos em execução no sistema"""

    field_names = ["NAME", "PID", "STARTED", "MEM%", "CPU%", "STATUS"]
    colums_styles = PLAIN_COLUMNS

    table = pretty_table(colums_styles, field_names)

    process_name_list = []

    result = use_case_process.list_process()
    
    if result is not None:
        for each_proc in result:
            if each_proc is None:
                continue
            process_name = each_proc['name']
            process_pid = each_proc['pid']
            process_started = each_proc['started']
            process_memory = each_proc['memory_percent']
            process_cpu = each_proc['cpu_percent']

            process_name_list.append(process_name)

            running = [colored("🟢 {}".format(process_name), 'green'), colored("{}".format(process_pid), color='cyan'),
                    "started {}".format(process_started), "mem {}%".format(process_memory),
                    "cpu {}%".format(process_cpu), colored('running', color='yellow')]

            if name_service:
                if process_name.startswith(name_service):
                    table.add_row(running)
            else:
                table.add_row(running)

        for each in list_files():

            if each not in sorted(process_name_list):
                down = [colored("🔴 {}".format(each), 'red'), colored("-", color='cyan'), "-", "mem - %",
                        "cpu - %", colored('down', color='red')]
                if name_service:
                    if each.startswith(name_service):
                        table.add_row(down)
                else:
                    table.add_row(down)
    return table


def list_instances():
    """ Retorna uma lista com as instancias registardas"""

    field_names = ['INSTANCES', 'HOSTNAME', 'IPADDR', 'REGISTRED']
    colums_styles = SINGLE_BORDER
    title = 'REGISTRO DE INSTÂNCIAS'

    table = pretty_table(colums_styles, field_names, title=title)

    ipaddr = host_name.ip_addr_or_hostname[0]
    hostname = host_name.ip_addr_or_hostname[1]

    list_instance_use_case = use_case_instances

    instances_registred = []

    for each in list_instance_use_case.list_instances({'nome': 'instances'}, {'_id': 0, 'nome': 0}):
        for server in each['servers']:
            for inst in server['instances']:
                if hostname in server['hostname'] or ipaddr in server['ipaddr']:
                    instances_registred.append(inst['instance'])
                    table.add_row([colored(inst['instance'], color='green'), server['hostname'], server['ipaddr'],
                                   colored('TRUE', 'green')])

    for instance in list_files():
        if instance not in instances_registred:
            table.add_row([colored(instance, color='red'), hostname, ipaddr, colored('FALSE', 'red')])

    return table


def is_running():
    """ Retorna uma lista de processos em execução"""
    process_name_list = []
    process_dict = {}

    for each_proc in use_case_process.list_process():
        if each_proc is None:
            continue
        
        process_name = each_proc['name']
        process_pid = each_proc['pid']

        process_name_list.append(process_name)
        process_dict[process_name] = process_pid

    return process_name_list


def get_file_pid(_path, file_name=None):
    """ Retorna os arquivos de PID"""
    r_path = os.path.join(_path, file_name)
    for filename in glob.glob("{}/*.pid".format(_path)):
        if filename.startswith(r_path):
            yield filename


def remove_pid(_path, name_service=None):
    """ Remove arquivos de PID"""
    for pid_file in get_file_pid(_path, name_service):
        if os.path.exists(pid_file):
            try:
                os.remove(pid_file)
            except OSError as err:
                return err


def start_process(_service):
    """ Executa um processo colocando em background."""
    cmd = [_service, "start"]
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL)
    except subprocess.CalledProcessError as err:
        return err


def do_start(_name=None, _all=False):
    """ Inicia os processos"""

    for proc in list_files():
        if proc is None:
            continue
        
        if _name:
            if proc.startswith(_name):
                if proc in is_running():
                    print("🟢 Process {:<47}is already {}".format(colored(proc, 'green'), colored('running', 'green')))
                else:
                    print("🟡 Starting process: {:<60}{}".format(colored(proc, 'cyan'), colored('done', 'yellow')))
                    start_process(proc)
        if _all is True:
            if proc in is_running():
                print("🟢 Process {:<47}is already {}".format(colored(proc, 'green'), colored('running', 'green')))
            else:
                print("🟡 Starting process: {:<60}{}".format(colored(proc, 'cyan'), colored('done', 'yellow')))
                start_process(proc)


def do_stop(name_service=None):
    """ Responsável por parar os serviços """
    
    for proc in use_case_process.list_process():
        if proc is None:
            continue
        
        if name_service:
            if proc['name'].startswith(name_service):
                if psutil.pid_exists(proc['pid']):
                    print("🔴 Stoping process: {:<47} PID: {}".format(colored(proc['name'], 'cyan'),
                                                                    colored(proc['pid'], 'green')))
                    os.kill(proc['pid'], signal.SIGTERM)
                    remove_pid(PATH_PID, name_service)
                    sleep(0.1)

        else:
            if psutil.pid_exists(proc['pid']):
                print("🔴 Stoping process: {:<47} PID: {}".format(colored(proc['name'], 'cyan'),
                                                                colored(proc['pid'], 'green')))

                os.kill(proc['pid'], signal.SIGTERM)
                remove_pid(PATH_PID, proc['name'])
                sleep(0.1)


def do_restart(name_service):
    """ Responsável por einicia serviços """

    for _proc in use_case_process.list_process():
        if _proc is None:
            continue
        
        if name_service:
            if _proc['name'].startswith(name_service):
                if psutil.pid_exists(_proc['pid']):
                    print("🔴 Stoping process: {:<47} PID: {}".format(colored(_proc['name'], 'cyan'),
                                                                     colored(_proc['pid'], 'green')))
                    os.kill(_proc['pid'], signal.SIGTERM)
                    remove_pid(PATH_PID, name_service)
                    sleep(0.1)
                    print("🟡 Starting process: {:<60}{}".format(colored(_proc['name'], 'cyan'), colored('done', 'yellow')))
                    start_process(_proc['name'])
        else:
            if psutil.pid_exists(_proc['pid']):
                print("🔴 Stoping process: {:<47} PID: {}".format(colored(_proc['name'], 'cyan'),
                                                                 colored(_proc['pid'], 'green')))

                os.kill(_proc['pid'], signal.SIGTERM)
                remove_pid(PATH_PID, _proc['name'])
                sleep(0.1)
                print("🟡 Starting process: {:<60}{}".format(colored(_proc['name'], 'cyan'), colored('done', 'yellow')))
                start_process(_proc['name'])


def basename():
    """Retorna uma lista com basename dos arquivos"""
    list_services = []
    for files in use_case_files.list_files():
        service = os.path.basename(files)
        list_services.append(service)
    return list_services


def copy_file(file_source, file_target):
    """ Copia arquivos entre diretórios """
    try:
        shutil.copyfile(file_source, file_target)
    except FileNotFoundError as err:
        return err


def create_link(source: str, target: str) -> OSError:
    """ Cria um link simbolico para o script do serviço"""
    try:
        os.symlink(source, target, )
    except OSError as err:
        return err


def remove_file_or_linnk(file_or_link):
    """ Responsável por remover arquivos ou links simbólicos"""
    if os.path.isfile(file_or_link) or os.path.islink(file_or_link):
        try:
            os.remove(file_or_link)
        except FileExistsError as err:
            return err
    return


def template_service(service_name):
    """ Retorna um template com base no serviço instalado"""
    for service in basename():
        if service.startswith(service_name):
            try:
                if os.path.isfile(os.path.join(PATH_INITD, service)):
                    template = os.path.join(PATH_INITD, service)
                    return template
            except FileNotFoundError as err:
                return err


def list_range(n_range: list) -> list:
    """ Retorna uma lista com range númerico"""
    _start, end = n_range.split('-')
    _start, end = int(_start), int(end)

    number_list = []

    if _start < end:
        number_list.extend(range(_start, end))
        number_list.append(end)
    return number_list


def gen_port(service_name: str, script_path: str) -> str:
    """ Gera porta dinamicamente para os serviços HTTP """
    script_file = os.path.join(os.path.dirname(os.path.abspath(script_path)), service_name)

    sock = socket.socket()
    sock.bind(('', 0))

    new_port = sock.getsockname()[1]

    with open(script_file, 'r') as file:
        file_content = file.read()

    replace = file_content.replace('None', str(new_port))

    with open(script_file, 'w') as file:
        file.write(replace)
    file.close()
    return str(new_port)


def rendering(name, template_name=None, output_path=None, template_path=None, port=None):
    """ Renderiza templates de scripts"""
    try:
        loader = FileSystemLoader('{}'.format(template_path))
        env = Environment(loader=loader, autoescape=True)
        template = env.get_template(TEMPLATE)
        output_template = os.path.join(output_path, template_name)

        with open(output_template, "w") as script:
            render = template.render(name=name, port=port)
            script.write(render)
            script.close()
    except FileExistsError as err:
        return err


def create_service(name, service_name):
    """ Cria os serviços propriamente dito"""
    print(f"{term_color} Adicionando serviço {colored(service_name, 'green')}")

    rendering(name, template_name=service_name, output_path=PATH_INITD, template_path=PATH_SCRIPT)
    script_basename = os.path.join(PATH_INITD, service_name)
    os.chmod(script_basename, stat.S_IXUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH)
    link = os.path.join(PATH_SBIN, service_name)
    create_link(script_basename, link)

    if name.startswith(BRAIN) or name.startswith(RENDER):
        gen_port(service_name, script_basename)


def normalize_name_service(name):
    """ Normaliza o nome do serviço para verificar se está na lista"""
    if PREFIX in name:
        name = name[2::]
    return name


def add_single_service(name):
    """ Adiciona serviços invidualmente"""
    source = normalize_name_service(name)
    for n in use_case_dirs.list_dirs:
        if source.startswith(n):
            if name in basename():
                print(f"{term_color} Serviço {colored(name, 'green')} já existe!")
                sys.exit(1)
            create_service(n, name)


def add_mulple_service(name, between=None):
    """Adiciona um range de serviço"""
    full_name = name
    name = normalize_name_service(name)

    if name.startswith(BRAIN):
        name = re.findall(BRAIN, name)[0]

    if name in use_case_dirs.list_dirs:
        if name and between:
            for number in list_range(between):
                service_name = PREFIX + name + "-" + str(number)

                if name == BRAIN:
                    service_name = full_name + "-" + str(number)

                if service_name in basename():
                    print(f"{term_color} Serviço {colored(service_name, 'green')} já existe!")
                    continue
                create_service(name, service_name)
                time.sleep(0.2)
    return


def remove_single_or_more_service(service):
    """ Responsável por remover um serviço individualmente ou um range"""
    source = os.path.join(PATH_INITD, service)
    dest = os.path.join(PATH_SBIN, service)

    if source:
        print(f"{term_color} Removendo serviço {colored(service, 'green')}")
        print(f"{term_color} Removendo arquivo {colored(source, 'blue')}")
        remove_file_or_linnk(source)

    if os.path.islink(dest):
        print(f"{term_color} Removendo link {colored(dest, 'cyan')}")
        remove_file_or_linnk(dest)

    return


def to_remove(name, between=None):
    """Remove um range de serviços"""
    if name and between:
        for number in list_range(between):
            service_name = name + "-" + str(number)
            if service_name not in basename():
                print(f"{term_color} Serviço {colored(service_name, 'green')} não encontrado.")
                continue

            remove_single_or_more_service(service_name)
            time.sleep(0.2)

    if name and name in basename():
        remove_single_or_more_service(name)
    else:
        print(f"{term_color} Serviço {colored(name, 'green')} não encontrado.")
    return


def view_params(service):
    """ Retorna os parametros de execução"""
    table = pretty_table(columns=SINGLE_BORDER, fields=['PARAMETER', 'VALUE'], title='PARÂMETROS DE EXECUÇÃO')

    for p in use_case_process.list_process():
        if p is None:
            continue
        
        if service == p['name']:
            argument = p['arguments']
            arguments = argument[2::]
            params = p['parameters']
        
            for i, param in enumerate(params):
                if i < len(arguments):
                    table.add_row([colored(param, 'cyan'), colored(arguments[i], 'green')])
    return table


def view_conectios(service):
    """ Responsável por exibir todas as conexões ativas de um serviço"""
    table = pretty_table(columns=SINGLE_BORDER, fields=['LADDR', 'LPORT', 'RADDR', 'RPORT', 'STATUS'],
                         title='CONEXÕES')

    for c in use_case_process.list_process():
        if c is None:
            continue
        
        service_name = c['name']
        if service == service_name:
            connections = c['connections']
            for i in connections:
                _status = i[5]
                laddr = i[3][0]
                if laddr == '::':
                    continue
                if _status == 'LISTEN':
                    laddr = i[3][0]
                    lport = i[3][1]
                    table.add_row([colored(laddr, 'green'), colored(lport, 'cyan'), '', '', colored(_status, 'cyan')])
                laddr = i[3][0]
                lport = i[3][1]
                raddr = i[4]
                if not raddr:
                    continue
                raddr = i[4][0]
                rport = i[4][1]
                table.add_row([colored(laddr, 'green'), colored(lport, 'cyan'), colored(raddr, 'green'),
                               colored(rport, 'cyan'), colored(_status, 'yellow')])
    return table


def view_env(service):
    """ Responsável por exibir uma tabela com todas as variáveis carregadas"""
    table = pretty_table(columns=SINGLE_BORDER, fields=['ENVIRON', 'VALUE'], title='VARIÁVEIS DE AMBIENTE')
    for e in use_case_process.list_process():
        if e is None:
            continue
        
        service_name = e['name']
        environ = e['environ']

        if service == service_name:
            for k, v in environ.items():
                if k.startswith('CS'):
                    table.add_row([colored(k, 'cyan'), colored(v, 'green')])
    return table


def documents(hostname=None, ipaddr=None, component=None, instance=None, _type=None):
    """ Retorna um dicionário com dados das instancias"""
    _repo_instance = DitcInstanceRepo(component=component, instance=instance, type=_type)

    if hostname and ipaddr and component:
        _repo_instance = DitcInstanceRepo(hostname=hostname, instances=[_repo_instance.__dict__], ipaddr=ipaddr)

    return _repo_instance.__dict__


def registry_service(instance=None, component=None, _type=None, flag=None):
    """ Responsável por registrar instancias no mongodb"""
    warning = "AVISO! Não foi possível registrar a instância"

    ipaddr = host_name.ip_addr_or_hostname[0]
    hostname = host_name.ip_addr_or_hostname[1]

    fmt_instance, fmt_ipaddr = colored(instance, 'green'), colored(ipaddr, 'cyan')

    data_list = []

    for i in use_case_instances.list_instances({'nome': 'instances'}, {'_id': 0, 'nome': 0}):
        for indx in i['servers']:
            _index = i['servers'].index(indx)
            _value = i['servers'][_index]

            data_ipaddr = _value['ipaddr']
            data_list = [data_ipaddr]

        # Atualiza um hostname cadastrado
        if not flag:
            print(data_ipaddr)
            if ipaddr != data_ipaddr:
                print(f"{term_color} {warning} {fmt_instance}, host {fmt_ipaddr} não cadastrado.")
                break

            if ipaddr == data_ipaddr:
                data_instances = _value['instances']

                for inst in data_instances:
                    idx = data_instances.index(inst)
                    data_instance = _value["instances"][idx]['instance']
                    data_list.append(data_instance)

                if instance in data_list:
                    print(f"{term_color} {warning} {fmt_instance}, está instância já é rgistrada.")
                    print(f"{term_color} Exibindo registro de instâncias...")
                    print(list_instances())
                    break

                if instance != data_instance:
                    print(f"{term_color} Registrando instância {fmt_instance}...")
                    data = documents(component=component, instance=instance, _type=_type)
                    use_case_update.update_instances({'nome': 'instances'},
                                                     {"$addToSet": {f"servers.{_index}.instances": data}})
                    print(f"{term_color} Instancia {fmt_instance} registrada com sucesso!")
                    print(f"{term_color} Exibindo registro de instâncias...")
                    print(list_instances())

        # Cadastra um hostname
        if flag:
            if ipaddr == data_ipaddr:
                print(f"{term_color} {warning} {fmt_instance} e host {fmt_ipaddr} já cadastrados.")
                print(f"{term_color} Exibindo registro de instâncias...")
                print(list_instances())
                break

            if ipaddr != data_ipaddr:
                print(f"{term_color} Cadastrando instância {fmt_instance} e host {fmt_ipaddr}...")
                data = documents(hostname=hostname, ipaddr=ipaddr,
                                 component=component, instance=instance, _type=_type)

                use_case_update.update_instances({'nome': 'instances'}, {"$push": {'servers': data}})

                print(f"{term_color} Instância {fmt_instance} e host {fmt_ipaddr} registrados com sucesso!")
                print(f"{term_color} Exibindo registro de instâncias...")
                print(list_instances())


@click.group('cli')
def cli():
    ...


@cli.command('start')
@click.option('-a', '--all', is_flag=True, help="Inicia todos os serviços")
@click.option('-g', '--group', is_flag=True, help="Inicia um grupo serviços")
@click.argument('name', required=False)
def start(all, group, name):
    if all:
        do_start(_all=True)
    if group:
        do_start(name)


@cli.command('stop')
@click.option('-a', '--all', is_flag=True, help="Para todos os serviços")
@click.option('-g', '--group', is_flag=True, help="Para um grupo serviços")
@click.argument('name', required=False)
def stop(all, group, name):
    if all:
        do_stop(name)
    if group:
        do_stop(name)


@cli.command('status')
@click.option('-a', '--all', is_flag=True, help="Exibe o status de todos os serviços")
@click.option('-g', '--group', is_flag=True, help="Exibe o status de um grupo serviços")
@click.argument('name', required=False, type=str)
def status(all, group, name):
    if all:
        print(do_status())
    if group:
        if isinstance(name, str):
            print(do_status(name))
        else:
            print(f"{term_color} AVISO! Argumento 'nome-do-serviço' obrigatório.")
            print(f"{term_color} Exemplo: csctl status -g cstasks")
            print(f"{term_color} Use: csctl status --help para obter ajuda.")
            sys.exit(1)


@cli.command('restart')
@click.option('-a', '--all', is_flag=True, help="Reinicia todos os serviços")
@click.option('-g', '--group', is_flag=True, help="Reinicia um grupo serviços")
@click.argument('name', required=False)
def restart(all, group, name):
    if all:
        do_restart(name)
    if group:
        do_restart(name)


@cli.command('add')
@click.option('-b', '--between', help="Adiciona um range de serviços")
@click.option('-s', '--single', is_flag=True, help="Adiciona um serviço individual")
@click.argument('name', required=False)
def add(name, between, single):
    if name and between:
        add_mulple_service(name, between)
    if name and single:
        add_single_service(name)


@cli.command('remove')
@click.option('-b', '--between', help="Remove um range de serviços")
@click.option('-s', '--single', is_flag=True, help="Remove um serviço individual")
@click.argument('name', required=False)
def remove(name, between, single):
    if between:
        to_remove(name, between)
    if name and single:
        to_remove(name)


@cli.command('show')
@click.option('-e', '--env', is_flag=True, help="Exibe as variáveis de ambiente")
@click.option('-p', '--params', is_flag=True, help="Exibe os parametros de execução")
@click.option('-c', '--conn', is_flag=True, help="Exibe as conexões estabelecidas")
@click.option('-r', '--registry', is_flag=True, help="Exibe o reistro das instâncias")
@click.argument('name', required=False)
def show(name, env, params, conn, registry):
    if registry and not name:
        print(list_instances())

    if name:
        if env:
            print(view_env(name))
        if params:
            print(view_params(name))
        if conn:
            print(view_conectios(name))
    elif not name:
        print(f"{term_color} AVISO! Argumento obrigatório [nome-do-serviço].")
        sys.exit(1)


@cli.command('registry')
@click.option('-c', '--component', help="Nome do componente")
@click.option('-i', '--instance',  help="Nome da instancia ou serviço")
@click.option('-t', '--type_service',  help="Tipo da instancia, MS ou REST")
@click.option('-a', '--add_host', help="Indica sé é para cadastrar tudo incluindo hostname")
def regystry(component, instance, type_service, add_host):
    if add_host:
        registry_service(instance=instance, component=component, _type=type_service, flag=add_host)

    if not add_host:
        registry_service(instance=instance, component=component, _type=type_service)


def main():
    cli()


if __name__ == '__main__':
    if sys.version_info >= (3, 6):
        try:
            main()
        except SystemError as error:
            raise error
    else:
        print("Versão do Python {} não suportada!".format(sys.version.split('\n')[0]))
        print("Versão suportada 3.6.16+")
        sys.exit(1)
