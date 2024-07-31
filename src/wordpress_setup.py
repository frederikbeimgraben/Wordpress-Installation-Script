#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# =============================================================================
# author:  Frederik Beimgraben
# email:   frederik@beimgraben.net
# date:    2024-07-31
# license: GPL-3.0
# version: 1.4.0
# =============================================================================
# Copyright (C) 2024 Frederik Beimgraben
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
# =============================================================================
# Have fun using the script! But be careful, it might overwrite existing files!
# =============================================================================

from enum import Enum
import os
import sys
import secrets
import argparse
import readline
import socket
import time
import requests
import subprocess
import shutil
import functools
import re
from typing import Any, Optional, Callable, Tuple, Dict, Union

# Constants:
HOSTNAME: str = 'localhost'
PORT: int = 8080
MNT_FOLDER: str = 'db_data'
DB_PASSWD: Optional[str] = None
DB_PASSWD_ROOT: Optional[str] = None

SILENT: bool = False

HOSTNAME_REGEX: str = r'^([a-zA-Z0-9]+\.)*[a-zA-Z0-9]+$'
PORT_REGEX: str = r'^[0-9]{1,5}$'
PATH_REGEX: str = r'^([^ \t\n\\]|/[^ \t\n\\])*(/[^ \t\n\\])?$'

class Level(Enum):
    SUCCESS = 0
    INFO = 1
    WARN = 2
    ERROR = 3

def print_log_fancy(type: Level, message: str) -> None:
    prefix: str

    if type == Level.SUCCESS:
        prefix = '[ \033[32mOK  \033[0m ]'
    elif type == Level.INFO:
        prefix = '[ INFO ]'
    elif type == Level.WARN:
        prefix = '[ \033[33mWARN\033[0m ]'
    elif type == Level.ERROR:
        prefix = '[ \033[31mERR \033[0m ]'
    else:
        prefix = '[ ???? ]'

    print(f'{prefix} {message}')

class CheckMode(Enum):
    THROW_ERROR = 1
    THROW_WARN = 2
    EXIT = 3

# Decorator for checks methods
def check(
        mode: CheckMode,
        interactive: bool = True,
        callback: Optional[Callable[..., bool]] = None,
        callback_args: Optional[Tuple] = None,
        callback_kwargs: Optional[Dict[str, Any]] = None,
        print_success: bool = False
    ) -> Callable[[Callable[..., Union[Tuple[bool, str], bool]]], Callable[...,Optional[bool]]]:
    def throw_handler(result: bool, message: Optional[str] = None) -> bool:
        if result:
            return True

        if mode == CheckMode.THROW_ERROR:
            raise AssertionError(message if message is not None else 'Check failed')

        if mode == CheckMode.EXIT:
            sys.exit(1)

        return False

    def interactive_handler(result: bool) -> bool:
        if not SILENT and mode == CheckMode.THROW_WARN and not result:
            if input('Do you want to continue? [y/N]: ').lower() != 'y':
                print_log_fancy(Level.ERROR, 'Aborted by user')
                return False
            else:
                return True

        return result

    def match_log_level(result: bool) -> Level:
        if mode == CheckMode.THROW_ERROR or mode == CheckMode.EXIT:
            return Level.ERROR if not result else Level.SUCCESS
        elif mode == CheckMode.THROW_WARN:
            return Level.WARN if not result else Level.SUCCESS

    def decorator(func: Union[Callable[..., Union[Tuple[bool, str], bool]], staticmethod, classmethod]) -> Callable[..., bool]:
        if not callable(func):
            # If staticmethod or classmethod is used, get the function
            if isinstance(func, staticmethod) or isinstance(func, classmethod):
                func = func.__func__
            else:
                raise AssertionError('Invalid function')

        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> bool:
            check_result = func(*args, **kwargs)

            message: Optional[str] = None

            if isinstance(check_result, tuple):
                message = check_result[1]
                check_result = check_result[0]

                if not check_result or print_success:
                    print_log_fancy(
                        match_log_level(check_result),
                        message
                    )

            if callback is not None:
                check_result = callback(
                    check_result,
                    *(callback_args if callback_args is not None else ()),
                    **(callback_kwargs if callback_kwargs is not None else {})
                )

            return throw_handler(
                interactive_handler(
                    check_result
                ),
                message
            )
        return wrapper
    return decorator

class Checks(object):
    @staticmethod
    @check(CheckMode.THROW_WARN, print_success=True)
    def not_already_configured() -> Tuple[bool, str]:
        # Assert, the files are not already present
        if os.path.isfile('.env') or os.path.isfile('docker-compose.yml') or os.path.isfile('.gitignore'):
            return False, 'Files already present in the directory'

        return True, 'Current directory is clean'

    @staticmethod
    @check(CheckMode.THROW_ERROR, print_success=True)
    def files_generated() -> Tuple[bool, str]:
        # Assert, the files are generated
        if not os.path.isfile('.env') or not os.path.isfile('docker-compose.yml') or not os.path.isfile('.gitignore'):
            return False, 'Files not generated'

        return True, 'Files generated'

    @staticmethod
    @check(CheckMode.THROW_ERROR)
    def nginx_config_installed(host: str) -> Tuple[bool, str]:
        # Assert, the files are generated
        path = f'/etc/nginx/sites-available/{host}.nginx.conf'

        if not os.path.isfile(path):
            return False, 'Nginx configuration not installed'

        return True, 'Nginx configuration installed'

    @staticmethod
    @check(CheckMode.THROW_ERROR, print_success=True)
    def nginx_config_enabled(host: str) -> Tuple[bool, str]:
        # Assert, the files are generated
        path = f'/etc/nginx/sites-enabled/{host}.nginx.conf'

        if not os.path.islink(path):
            return False, 'Nginx configuration not enabled'

        return True, 'Nginx configuration enabled'

    @staticmethod
    @check(CheckMode.THROW_ERROR)
    def user_is_root() -> Tuple[bool, str]:
        if os.geteuid() != 0:
            return False, 'This script must be run as root'

        return True, 'Running as root'

    @staticmethod
    @check(CheckMode.THROW_ERROR)
    def docker() -> Tuple[bool, str]:
        if not shutil.which('docker'):
            return False, 'Docker is not installed'

        return True, 'Docker is installed'

    @staticmethod
    @check(CheckMode.THROW_ERROR)
    def docker_compose() -> Tuple[bool, str]:
        if not shutil.which('docker-compose'):
            return False, 'Docker Compose is not installed'

        return True, 'Docker Compose is installed'

    @staticmethod
    @check(CheckMode.THROW_ERROR, interactive=True)
    def docker_daemon() -> Tuple[bool, str]:
        if not os.system('docker info > /dev/null 2>&1') == 0:
            return False, 'Docker is not running'

        return True, 'Docker is running'

    @staticmethod
    @check(
        CheckMode.THROW_WARN,
        interactive=True,
        print_success=True,
    )
    def dns(hostname: str) -> Tuple[bool, str]:
        latch: bool = False

        while True:
            try:
                try:
                    socket.gethostbyname(hostname)
                    break
                except socket.gaierror:
                    if not latch:
                        latch = True
                        print_log_fancy(Level.INFO, 'Waiting for DNS to resolve for {hostname}. Press CTRL+C to proceed without waiting...')
                    time.sleep(1)
            except KeyboardInterrupt:
                return True, 'Continuing without waiting for DNS to resolve'

        Checks.dns_mismatch(hostname)

        return True, 'DNS is set up correctly'

    @staticmethod
    @check(CheckMode.THROW_WARN, interactive=True, print_success=True)
    def dns_mismatch(hostname: str) -> Tuple[bool, str]:
        # Get public IP of this machine - if they dont match, warn the user
        if socket.gethostbyname(hostname) != requests.get('https://api.ipify.org').text:
            return False, f'Hostname does not resolve to this machine\'s public IP: {socket.gethostbyname(hostname)} != {requests.get("https://api.ipify.org").text}'

        return True, 'Hostname resolves to this machine\'s public IP'

    @staticmethod
    @check(CheckMode.THROW_ERROR)
    def git() -> Tuple[bool, str]:
        if not shutil.which('git'):
            return False, 'Git is not installed'

        return True, 'Git is installed'

    @staticmethod
    @check(CheckMode.THROW_ERROR)
    def nginx() -> Tuple[bool, str]:
        if not shutil.which('nginx'):
            return False, 'Nginx is not installed'

        return True, 'Nginx is installed'

    @staticmethod
    @check(CheckMode.THROW_ERROR)
    def certbot() -> Tuple[bool, str]:
        if not shutil.which('certbot'):
            return False, 'Certbot is not installed'

        return True, 'Certbot is installed'

    @staticmethod
    @check(CheckMode.THROW_ERROR)
    def nginx_test_config() -> Tuple[bool, str]:
        if os.system('nginx -t') != 0:
            return False, 'Nginx configuration is invalid'

        return True, 'Nginx configuration is valid'

    @staticmethod
    @check(CheckMode.THROW_ERROR)
    def systemd() -> Tuple[bool, str]:
        if not shutil.which('systemctl'):
            return False, 'Systemd is not installed'

        return True, 'Systemd is installed'

    @staticmethod
    @check(CheckMode.THROW_ERROR)
    def perform_checks_exit(*checks: Union[Callable[..., bool], bool]) -> bool:
        try:
            if not all(check() if callable(check) else check for check in checks):
                print_log_fancy(Level.ERROR, 'Checks failed')
                sys.exit(1)
            return True
        except KeyboardInterrupt:
            print_log_fancy(Level.WARN, 'User interrupted the script')
            sys.exit(1)
        except AssertionError as e:
            print_log_fancy(Level.ERROR, f'Assertion failed: {e}')
            sys.exit(1)

    @staticmethod
    @check(CheckMode.THROW_ERROR)
    def type_convertable(arg: str, T: Any = str, regex: Optional[str] = None):
        try:
            if regex is not None:
                assert re.match(regex, arg)
            T(arg)
        except (ValueError, AssertionError):
            return False, f'Argument {arg} is not convertable to type {T.__name__}'
        return True, ''

    @staticmethod
    @check(CheckMode.THROW_ERROR, print_success=True)
    def current_folder_writeable():
        try:
            with open('test', 'w') as f:
                f.write('test')
            os.remove('test')
        except PermissionError:
            return False, 'Current folder is not writeable'
        return True, 'Current folder is writeable'

    @staticmethod
    @check(CheckMode.THROW_ERROR)
    def file_exists(path: str):
        if not os.path.exists(path):
            return False, f'File {path} does not exist'
        return True, f'File {path} exists'

    @staticmethod
    @check(CheckMode.THROW_ERROR)
    def conflicting_args(*args: Optional[Union[str, bool]]):
        if len([arg for arg in args if arg is not None and arg is not False]) > 1:
            return False, 'Conflicting arguments'
        return True, 'No conflicting arguments'

class Actions:
    @staticmethod
    def install_nginx_conf(hostname: str) -> None:
        print_log_fancy(Level.INFO, 'Installing Nginx configuration...')

        # Copy the file to /etc/nginx/sites-available
        shutil.copy(f'{hostname}.nginx.conf', f'/etc/nginx/sites-available/{hostname}.nginx.conf')
        # Create the symlink
        if os.path.islink(f'/etc/nginx/sites-enabled/{hostname}.nginx.conf'):
            os.remove(f'/etc/nginx/sites-enabled/{hostname}.nginx.conf')
        os.symlink(f'/etc/nginx/sites-available/{hostname}.nginx.conf', f'/etc/nginx/sites-enabled/{hostname}.nginx.conf')

        print_log_fancy(Level.SUCCESS, 'Nginx configuration installed')

    @staticmethod
    def restart_nginx() -> None:
        print_log_fancy(Level.INFO, 'Restarting Nginx...')

        os.system('systemctl restart nginx')

        print_log_fancy(Level.SUCCESS, 'Nginx restarted')

    @staticmethod
    def revert_nginx_conf(hostname: str) -> None:
        print_log_fancy(Level.INFO, 'Reverting Nginx configuration...')

        # Remove the symlink
        os.remove(f'/etc/nginx/sites-enabled/{hostname}.nginx.conf')

        # Remove the file
        os.remove(f'/etc/nginx/sites-available/{hostname}.nginx.conf')

        print_log_fancy(Level.SUCCESS, 'Nginx configuration reverted')

    @staticmethod
    def create_sites_if_not_exists() -> None:
        if not os.path.exists('/etc/nginx/sites-available'):
            os.mkdir('/etc/nginx/sites-available')
            print_log_fancy(Level.INFO, 'Created sites-available')
        if not os.path.exists('/etc/nginx/sites-enabled'):
            os.mkdir('/etc/nginx/sites-enabled')
            print_log_fancy(Level.INFO, 'Created sites-enabled')

    @staticmethod
    def generate_nginx_conf(
            hostname: str = 'localhost',
            port: int = 8080,
            internal_host: str = '127.0.0.1'
        ) -> str:
        return \
f"""server {{
    listen 80;
    server_name {hostname};

    location / {{
        proxy_pass http://{internal_host}:{port};
        proxy_redirect http://{internal_host}:{port} https://{hostname};

        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

        proxy_set_header Host $host;

        proxy_cookie_domain http://{internal_host}:{port} {hostname};
        proxy_set_header X-Forwarded-Proto https;
    }}
}}"""

    @staticmethod
    def create_nginx_conf(
            hostname: str = 'localhost',
            port: int = 8080,
            internal_host: str = 'localhost'
        ) -> None:
        with open(f'{hostname}.nginx.conf', 'w') as f:
            f.write(Actions.generate_nginx_conf(hostname, port, internal_host))
        print_log_fancy(Level.SUCCESS, 'Nginx configuration created')

    @staticmethod
    def generate_docker_compose() -> str:
            return \
"""
services:
    db:
        image: mariadb:10.6.4-focal
        command: '--default-authentication-plugin=mysql_native_password'
        volumes:
            - ${DB_MNT}:/var/lib/mysql
        restart: always
        environment:
            - MYSQL_ROOT_PASSWORD=${DB_ROOT_PASSWD}
            - MYSQL_DATABASE=wordpress
            - MYSQL_USER=wordpress
            - MYSQL_PASSWORD=${DB_PASSWD}
        expose:
            - 3306

    wordpress:
        image: wordpress:latest
        ports:
            - ${HOST_PORT}:80
        restart: always
        depends_on:
            - db
        environment:
            - WORDPRESS_DB_HOST=db
            - WORDPRESS_DB_USER=wordpress
            - WORDPRESS_DB_PASSWORD=${DB_PASSWD}
            - WORDPRESS_DB_NAME=wordpress

volumes:
    db_data:"""

    @staticmethod
    def create_docker_compose() -> None:
        with open('docker-compose.yml', 'w') as f:
            f.write(Actions.generate_docker_compose())
        print_log_fancy(Level.SUCCESS, 'Docker Compose configuration created')

    @staticmethod
    def generate_dotenv(
            hostname: str = 'localhost',
            port: int = 8080,
            mnt_folder: str = 'db_data',
            db_passwd: Optional[str] = None,
            db_passwd_root: Optional[str] = None
        ) -> str:
        # Create a safe password for the database
        if db_passwd is None:
            db_passwd = secrets.token_urlsafe(16)
        if db_passwd_root is None:
            db_passwd_root = secrets.token_urlsafe(16)

        return \
f"""DB_MNT={mnt_folder}
DB_ROOT_PASSWD={db_passwd}
DB_PASSWD={db_passwd_root}
HOST_PORT={port}
HOSTNAME={hostname}"""

    @staticmethod
    def create_dotenv(
            hostname: str = 'localhost',
            port: int = 8080,
            mnt_folder: str = 'db_data',
            db_passwd: Optional[str] = None,
            db_passwd_root: Optional[str] = None
        ) -> None:
        with open('.env', 'w') as f:
            f.write(Actions.generate_dotenv(hostname, port, mnt_folder, db_passwd, db_passwd_root))
        print_log_fancy(Level.SUCCESS, '.env file created')

    @staticmethod
    def generate_dotgitignore(mnt_folder) -> str:
        return \
f"""
# Ignore the database data folder
{mnt_folder}/"""

    @staticmethod
    def create_dotgitignore(mnt_folder) -> None:
        with open('.gitignore', 'w') as f:
            f.write(Actions.generate_dotgitignore(mnt_folder))
        print_log_fancy(Level.SUCCESS, '.gitignore created')

    @staticmethod
    def git_init() -> None:
        os.system('git init')

    @staticmethod
    def remove_git() -> None:
        os.system('rm -rf .git')
        print_log_fancy(Level.SUCCESS, 'Removed .git')

    @staticmethod
    def convert_argument(
            arg: str,
            T: Any = str,
            default: Optional[Any] = None,
            regex: Optional[str] = None
        ) -> Any:
        Checks.perform_checks_exit(Checks.type_convertable(arg, T, regex))

        if T == str or T == int or T == float or T == bool:
            return T(arg)
        elif T == os.PathLike:
            return T(arg)
        else:
            raise NotImplementedError(f'Unsupported type: {T}')

    @staticmethod
    def input_with_default(prompt: str, default: Optional[str]) -> str:
        # Already write default value into input using readline
        if default is not None:
            readline.set_startup_hook(lambda: readline.insert_text(default))
        result = input(prompt)

        # Reset startup hook
        readline.set_startup_hook()

        return result

    # Refactor of get_user_input_with_default()
    @staticmethod
    def get_user_input(
            T: Any,
            prompt: str,
            default: Any = None,
            default_editable: bool = True,
            regex: Optional[str] = None
        ) -> Any:

        return_value: Any = None

        # Get user input, check and retry if necessary
        while True:
            try:
                if default_editable:
                    return_value = Actions.convert_argument(
                        Actions.input_with_default(f'{prompt}: ', str(default)),
                        T,
                        default,
                        regex
                    )
                else:
                    return_value = Actions.convert_argument(
                        input(f'{prompt} [{default}]: '),
                        T,
                        default,
                        regex
                    )
                break
            except (ValueError, AssertionError):
                print_log_fancy(Level.ERROR, 'Invalid input')

        print_log_fancy(Level.INFO, f'Got input: {return_value}')

        return return_value

    # Refactor of interactive()
    @staticmethod
    def configure_interactive(defaults: Dict[str, Any]) -> Dict[str, Any]:
        # Get values
        hostname: str = Actions.get_user_input(str, 'Hostname', defaults['hostname'], regex=HOSTNAME_REGEX)
        port: int = Actions.get_user_input(int, 'Port', defaults['port'], regex=PORT_REGEX)
        mnt_folder: str = Actions.get_user_input(str, 'Mount folder', defaults['mnt_folder'], regex=PATH_REGEX)

        db_passwd: str = Actions.get_user_input(str, 'Database password', defaults['db_passwd'])
        db_passwd_root: str = Actions.get_user_input(str, 'Database root password', defaults['db_passwd_root'])

        return {
            'hostname': hostname,
            'port': port,
            'mnt_folder': mnt_folder,
            'db_passwd': db_passwd,
            'db_passwd_root': db_passwd_root
        }

    @staticmethod
    def configure(args: argparse.Namespace) -> Dict[str, Any]:
        # Get CLI arguments
        existing = {
            'hostname': args.hostname,
            'port': args.port,
            'mnt_folder': args.mnt_folder,
            'db_passwd': secrets.token_urlsafe(16) if args.db_passwd is None else args.db_passwd,
            'db_passwd_root': secrets.token_urlsafe(16) if args.db_passwd_root is None else args.db_passwd_root
        }

        # Get interactive values
        if args.interactive:
            print_log_fancy(Level.INFO, 'Entering interactive mode...')
            existing = Actions.configure_interactive(existing)

        print_log_fancy(Level.INFO, \
f"""Configuration:
\t\tHostname:     {existing['hostname']}
\t\tPort:         {existing['port']}
\t\tMount folder: {existing['mnt_folder']}
\t\tDB password:  {existing['db_passwd']}
\t\tDB root pass: {existing['db_passwd_root']}""")
        
        return existing

    @staticmethod
    def make_configs(
            hostname: str,
            port: int,
            mnt_folder: str,
            db_passwd: str,
            db_passwd_root: str
        ) -> None:
        Checks.perform_checks_exit(
            Checks.current_folder_writeable,
            Checks.not_already_configured
        )

        print_log_fancy(Level.INFO, 'Generating files...')

        Actions.create_dotgitignore(mnt_folder)
        Actions.git_init()
        Actions.create_docker_compose()
        Actions.create_dotenv(hostname, port, mnt_folder, db_passwd, db_passwd_root)
        Actions.create_nginx_conf(hostname, port)

        print_log_fancy(Level.SUCCESS, 'Files generated')

    @staticmethod
    def install(
            hostname: str
        ) -> None:

        print_log_fancy(Level.INFO, 'Installing...')

        required_files = ['docker-compose.yml', '.env', f'{hostname}.nginx.conf']

        Checks.perform_checks_exit(
            Checks.user_is_root,
            Checks.docker,
            Checks.docker_compose,
            Checks.docker_daemon,
            Checks.nginx,
            Checks.nginx_test_config,
            Checks.systemd,
            *map(Checks.file_exists, required_files)
        )

        # Run docker-compose
        print_log_fancy(Level.INFO, 'Running docker-compose...')
        try:
            subprocess.run(['docker-compose', 'up', '-d'], check=True)
        except subprocess.CalledProcessError:
            print_log_fancy(Level.ERROR, 'Failed to run docker-compose')
            sys.exit(1)
        print_log_fancy(Level.SUCCESS, 'Docker-compose complete')

        # Create sites-available and sites-enabled if they don't exist
        print_log_fancy(Level.INFO, 'Creating sites-available and sites-enabled...')
        Actions.create_sites_if_not_exists()
        print_log_fancy(Level.SUCCESS, 'sites-available and sites-enabled created or already present')

        # Copy Nginx config
        print_log_fancy(Level.INFO, 'Copying Nginx config...')
        shutil.copy(f'{hostname}.nginx.conf', f'/etc/nginx/sites-available/{hostname}.nginx.conf')
        print_log_fancy(Level.SUCCESS, 'Nginx config copied')

        # Enable site
        print_log_fancy(Level.INFO, 'Enabling site...')
        if os.path.exists(f'/etc/nginx/sites-enabled/{hostname}.nginx.conf'):
            os.remove(f'/etc/nginx/sites-enabled/{hostname}.nginx.conf')
        os.symlink(f'/etc/nginx/sites-available/{hostname}.nginx.conf', f'/etc/nginx/sites-enabled/{hostname}.nginx.conf')
        print_log_fancy(Level.SUCCESS, 'Site enabled')

        # Reload Nginx
        print_log_fancy(Level.INFO, 'Reloading Nginx...')
        Actions.restart_nginx()
        print_log_fancy(Level.SUCCESS, 'Nginx reloaded')

        print_log_fancy(Level.SUCCESS, 'Installation complete')

    @staticmethod
    def cleanup() -> None:
        print_log_fancy(Level.INFO, 'Cleaning up...')

        print_log_fancy(Level.INFO, 'Stopping docker containers and removing volumes...')

        if os.system('docker-compose down --volumes') != 0:
            print_log_fancy(Level.ERROR, 'Failed to stop docker containers')
            sys.exit(1)
        
        print_log_fancy(Level.SUCCESS, 'Docker containers stopped and volumes removed')
        
        os.remove('.env')
        os.remove('docker-compose.yml')
        os.remove('.gitignore')

        for file in os.listdir('.'):
            if file.endswith('.nginx.conf'):
                os.remove(file)

        print_log_fancy(Level.SUCCESS, 'Files removed')


        print_log_fancy(Level.SUCCESS, 'Cleanup complete')

    @staticmethod
    def get_hostname_from_dotenv() -> str:
        print_log_fancy(Level.INFO, 'Getting hostname from .env...')

        with open('.env', 'r') as f:
            for line in f:
                if line.startswith('HOSTNAME'):
                    hostname = line.split('=')[1].strip()

                    print_log_fancy(Level.SUCCESS, f'Got hostname: {hostname}')

                    return hostname
        
        print_log_fancy(Level.ERROR, 'Failed to get hostname from .env')

        raise FileNotFoundError('.env')

    @staticmethod
    def uninstall() -> None:
        print_log_fancy(Level.INFO, 'Uninstalling...')

        hostname = Actions.get_hostname_from_dotenv()

        target_files = [
            f'/etc/nginx/sites-available/{hostname}.nginx.conf',
            f'/etc/nginx/sites-enabled/{hostname}.nginx.conf'
        ]

        # Perform checks
        Checks.perform_checks_exit(
            Checks.file_exists('.env'),
            Checks.file_exists('docker-compose.yml'),
            Checks.file_exists('.gitignore'),
            Checks.file_exists(f'/etc/nginx/sites-available/{hostname}.nginx.conf'),
            Checks.user_is_root,
            Checks.docker,
            Checks.docker_compose,
            Checks.docker_daemon,
            Checks.nginx,
            Checks.systemd
        )

        # Delete target files
        for file in target_files:
            if os.path.exists(file):
                os.remove(file)

        try:
            # Stop the containers
            assert os.system('docker-compose down') == 0

            # Remove the nginx configuration
            Actions.revert_nginx_conf(hostname)

            # Reload nginx
            assert os.system('systemctl reload nginx') == 0
        except AssertionError:
            print_log_fancy(Level.ERROR, 'Failed to uninstall')
            sys.exit(1)

        print_log_fancy(Level.SUCCESS, 'Uninstall complete')

    @staticmethod
    def certbot(hostname: str) -> None:
        # Perform checks
        Checks.perform_checks_exit(
            Checks.nginx,
            Checks.certbot
        )

        Checks.dns(hostname)

        # Run certbot
        print_log_fancy(Level.INFO, 'Running certbot...')
        os.system(f'certbot --nginx -d {hostname}')
        print_log_fancy(Level.SUCCESS, 'Certbot complete')

argparser = argparse.ArgumentParser(description='Create a docker compose project for a wordpress site running behind a reverse proxy')
# Hostname: -n or --hostname
# Default: localhost
# Conflicts with: N/A
argparser.add_argument('-n', '--hostname', help='Hostname for the site', default=HOSTNAME)
# Port: -p or --port
# Default: 8080
# Conflicts with: N/A
argparser.add_argument('-p', '--port', help='Port for the site', default=PORT, type=int)
# Mount folder: -m or --mnt_folder
# Default: db_data
# Conflicts with: N/A
argparser.add_argument('-m', '--mnt_folder', help='Folder to mount the database', default=MNT_FOLDER)
# Database password: -d or --db_passwd
# Default: <random> (None)
# Conflicts with: N/A
argparser.add_argument('-d', '--db_passwd', help='Database password', default=DB_PASSWD)
# Database root password: -r or --db_passwd_root
# Default: <random> (None)
# Conflicts with: N/A
argparser.add_argument('-r', '--db_passwd_root', help='Database root password', default=DB_PASSWD_ROOT)
# Cleanup: -c or --cleanup
# Default: False
# Conflicts with: -U
argparser.add_argument('-c', '--cleanup', action='store_true', help='Cleanup the project')
# Install: -i or --install
# Default: False
# Conflicts with: -U
argparser.add_argument('-I', '--install', action='store_true', help='Install the project')
# Interactive: -I or --interactive
# Default: False
# Conflicts with: N/A
argparser.add_argument('-i', '--interactive', action='store_true', help='Interactive mode')
# Certbot: -C or --certbot
# Default: False
# Conflicts with: N/A
argparser.add_argument('-C', '--certbot', action='store_true', help='Install certbot')
# Uninstall: -U or --uninstall
# Default: False
# Conflicts with: -I, -C
argparser.add_argument('-U', '--uninstall', action='store_true', help='Uninstall the project')
# Silent: -s or --silent
# Default: False
# Conflicts with: N/A
# Don't show prompts
argparser.add_argument('-s', '--silent', action='store_true', help='Silent mode')

def main():
    try:
        args = argparser.parse_args()

        if args.silent:
            SILENT = True

        options = Actions.configure(args)

        Checks.conflicting_args(
            args.install,
            args.uninstall
        )

        Checks.conflicting_args(
            args.uninstall,
            args.certbot
        )

        if not any((args.install, args.uninstall, args.certbot, args.cleanup)):
            Actions.make_configs(**options)

        if args.cleanup and not args.uninstall:
            Actions.cleanup()

        if args.install:
            Actions.make_configs(**options)
            Actions.install(options['hostname'])

        if args.uninstall:
            Actions.uninstall()

            if args.cleanup:
                Actions.cleanup()

            sys.exit(0)

        if args.certbot:
            Checks.perform_checks_exit(
                Checks.nginx_config_installed(options['hostname']),
                Checks.nginx_config_enabled(options['hostname'])
            )

            Actions.certbot(options['hostname'])

        print_log_fancy(Level.SUCCESS, 'All actions completed successfully')
    except KeyboardInterrupt:
        print('\n')
        print_log_fancy(Level.ERROR, 'Installation aborted!')
        sys.exit(1)
    except AssertionError as e:
        print_log_fancy(Level.ERROR, f'Assertion failed: {e}')
        sys.exit(1)
    except Exception as e:
        print_log_fancy(Level.ERROR, f'An error occurred: {e}')
        sys.exit(1)


if __name__ == '__main__':
    main()