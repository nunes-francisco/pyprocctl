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
from dataclasses import dataclass
from typing import List, Dict, Optional, Any
from jinja2 import Environment, FileSystemLoader
from prettytable import PrettyTable, SINGLE_BORDER, PLAIN_COLUMNS
from termcolor import colored

from repository.mongo_repo import MongoRepo
from repository.inmemory_repo import (
    ListProcessRepo, ListFilesRepo, ListFieldsRepo, 
    ListDirRepo, DitcInstanceRepo
)
from usecases.list_istance import ListInstanceUseCase, UpdateInstanceUseCase
from usecases.list_process import ListProcessUseCase
from usecases.list_files import ListFileUseCase
from usecases.list_dirs import ListDirUseCase
from infra.config import Config
from infra.config_hostname import IpAddrOrHostname

@dataclass
class ServiceManager:
    """Manager class to handle service operations"""
    settings: Config
    host_name: IpAddrOrHostname
    logger: logging.Logger
    
    def __init__(self):
        self.settings = Config()
        self.host_name = IpAddrOrHostname()
        self.logger = self._setup_logger()
        self.term_color = f"{colored('>', 'white')}{colored('>', 'green')}{colored('>', 'magenta')}"
        self._init_repositories()
        
    def _setup_logger(self) -> logging.Logger:
        """Setup logging configuration"""
        logger = logging.getLogger("-")
        logger.setLevel(logging.INFO)
        
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        return logger
    
    def _init_repositories(self):
        """Initialize repositories and use cases"""
        self.repo_fields = ListFieldsRepo()
        self.repo_instance = MongoRepo(
            url=self.settings.MONGODB_URL,
            db=self.settings.DB_NAME,
            collection=self.settings.COLLECTION
        )
        self.repo_process = ListProcessRepo(self.repo_fields.fields)
        self.repo_files = ListFilesRepo(self.settings.PREFIX, self.settings.PATH_INITD)
        self.repo_dirs = ListDirRepo(self.settings.PATH_CORTEX)
        
        self.use_case_files = ListFileUseCase(self.repo_files)
        self.use_case_dirs = ListDirUseCase(self.repo_dirs)
        self.use_case_process = ListProcessUseCase(self.repo_process)
        self.use_case_instances = ListInstanceUseCase(self.repo_instance)
        self.use_case_update = UpdateInstanceUseCase(self.repo_instance)

    def create_pretty_table(self, columns: str, fields: List[str], title: Optional[str] = None) -> PrettyTable:
        """Create and configure a PrettyTable instance"""
        table = PrettyTable()
        if title:
            table.title = colored(title, 'magenta')
        table.set_style(columns)
        table.field_names = fields
        table.align = "l"
        return table

    def get_running_processes(self) -> Dict[str, int]:
        """Get dictionary of running processes with their PIDs"""
        processes = {}
        for proc in self.use_case_process.list_process():
            processes[proc['name']] = proc['pid']
        return processes

    def manage_process(self, action: str, name: Optional[str] = None, all_services: bool = False):
        """Unified process management method"""
        running_processes = self.get_running_processes()
        
        if action not in ['start', 'stop', 'restart']:
            raise ValueError(f"Invalid action: {action}")
            
        services = [name] if name else self.list_files()
        if not all_services and not name:
            return
            
        for service in services:
            if not service.startswith(name) and name:
                continue
                
            if action == 'start':
                if service in running_processes:
                    self.logger.info(f"🟢 Process {service} is already running")
                else:
                    self._start_single_process(service)
                    
            elif action == 'stop':
                if service in running_processes:
                    self._stop_single_process(service, running_processes[service])
                    
            elif action == 'restart':
                if service in running_processes:
                    self._stop_single_process(service, running_processes[service])
                    time.sleep(0.1)
                    self._start_single_process(service)

    def _start_single_process(self, service: str):
        """Start a single service process"""
        self.logger.info(f"🟡 Starting process: {service}")
        try:
            subprocess.run([service, "start"], stdout=subprocess.DEVNULL)
        except subprocess.CalledProcessError as err:
            self.logger.error(f"Failed to start {service}: {err}")

    def _stop_single_process(self, service: str, pid: int):
        """Stop a single service process"""
        self.logger.info(f"🔴 Stopping process: {service} (PID: {pid})")
        try:
            os.kill(pid, signal.SIGTERM)
            self._remove_pid_file(service)
        except ProcessLookupError:
            self.logger.warning(f"Process {pid} not found")

    def _remove_pid_file(self, service: str):
        """Remove PID file for a service"""
        pid_path = os.path.join(self.settings.PATH_PID, f"{service}.pid")
        try:
            if os.path.exists(pid_path):
                os.remove(pid_path)
        except OSError as err:
            self.logger.error(f"Failed to remove PID file: {err}")

    def create_service(self, name: str, service_type: str = 'single', range_str: Optional[str] = None):
        """Create new service(s)"""
        if service_type == 'range' and range_str:
            self._create_service_range(name, range_str)
        else:
            self._create_single_service(name)

    def _create_single_service(self, name: str):
        """Create a single service"""
        if name in self.list_files():
            self.logger.warning(f"Service {name} already exists")
            return
            
        self._render_and_setup_service(name)

    def _create_service_range(self, name: str, range_str: str):
        """Create multiple services in a range"""
        start, end = map(int, range_str.split('-'))
        for num in range(start, end + 1):
            service_name = f"{self.settings.PREFIX}{name}-{num}"
            self._create_single_service(service_name)
            time.sleep(0.2)

    def _render_and_setup_service(self, name: str):
        """Render template and setup service files"""
        template_loader = FileSystemLoader(self.settings.PATH_SCRIPT)
        env = Environment(loader=template_loader, autoescape=True)
        
        template = env.get_template(self.settings.TEMPLATE)
        output_path = os.path.join(self.settings.PATH_INITD, name)
        
        with open(output_path, "w") as f:
            f.write(template.render(
                name=name,
                port=self._generate_port() if self._needs_port(name) else None
            ))
            
        os.chmod(output_path, stat.S_IXUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH)
        self._create_symlink(output_path, os.path.join(self.settings.PATH_SBIN, name))

    def _needs_port(self, name: str) -> bool:
        """Check if service needs a port assignment"""
        return any(name.startswith(prefix) for prefix in [self.settings.BRAIN, self.settings.RENDER])

    def _generate_port(self) -> int:
        """Generate an available port number"""
        sock = socket.socket()
        sock.bind(('', 0))
        return sock.getsockname()[1]

    def _create_symlink(self, source: str, target: str):
        """Create symbolic link for service"""
        try:
            if os.path.exists(target):
                os.remove(target)
            os.symlink(source, target)
        except OSError as err:
            self.logger.error(f"Failed to create symlink: {err}")

@click.group()
@click.pass_context
def cli(ctx):
    """Service Control CLI"""
    ctx.obj = ServiceManager()

@cli.command()
@click.option('-a', '--all', is_flag=True, help="Start all services")
@click.option('-g', '--group', help="Start a group of services")
@click.pass_obj
def start(manager: ServiceManager, all: bool, group: Optional[str]):
    """Start services command"""
    manager.manage_process('start', name=group, all_services=all)

@cli.command()
@click.option('-a', '--all', is_flag=True, help="Stop all services")
@click.option('-g', '--group', help="Stop a group of services")
@click.pass_obj
def stop(manager: ServiceManager, all: bool, group: Optional[str]):
    """Stop services command"""
    manager.manage_process('stop', name=group, all_services=all)

@cli.command()
@click.option('-a', '--all', is_flag=True, help="Restart all services")
@click.option('-g', '--group', help="Restart a group of services")
@click.pass_obj
def restart(manager: ServiceManager, all: bool, group: Optional[str]):
    """Restart services command"""
    manager.manage_process('restart', name=group, all_services=all)

def main():
    """Main entry point"""
    if sys.version_info >= (3, 6):
        try:
            cli()
        except Exception as error:
            logging.error(f"Error occurred: {error}")
            sys.exit(1)
    else:
        print(f"Python version {sys.version.split()[0]} not supported!")
        print("Supported version: 3.6.16+")
        sys.exit(1)

if __name__ == '__main__':
    main()
