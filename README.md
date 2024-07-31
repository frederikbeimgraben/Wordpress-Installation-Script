# Wordpress-Installation-Script
> ```bash
> # =============================================================================
> # Copyright (C) 2024 Frederik Beimgraben
> #
> # This program is free software: you can redistribute it and/or modify
> # it under the terms of the GNU General Public License as published by
> # the Free Software Foundation, either version 3 of the License, or
> # (at your option) any later version.
> #
> # This program is distributed in the hope that it will be useful,
> # but WITHOUT ANY WARRANTY; without even the implied warranty of
> # MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
> # GNU General Public License for more details.
> #
> # You should have received a copy of the GNU General Public License
> # along with this program.  If not, see <https://www.gnu.org/licenses/>.
> # =============================================================================
> ```

## Installation
### Using Makefile and Cython
```bash
# Compile the script to an executable using Cython:
make
# Copy the executable to a folder in your PATH (e.g. /usr/local/bin):
sudo cp wordpress_install /usr/local/bin/
```

### From PyPI
```bash
# Install the script from PyPI:
pip install wordpress-docker-setup
```

# WHAT IS THIS?
This is a script to create a docker-compose project for a wordpress site with a nginx reverse proxy. The script will create the configuration files for the project and start the containers as well as install the nginx reverse proxy configuration. *See the usage section for more information.*

# Usage
```txt
Usage of the script:
    python3 wordpress_setup.py [ { -I [ -C ] | -U } ] [ -n <hostname> ] [ -p <port> ] [ -m <mount_folder> ] [ -d <db_passwd> ] [ -r <db_passwd_root> ]

    [no action options]:
        Create configuration files for a new project in the current directory

    -I: Install the project
    -C: Start Certbot to get a certificate for the domain
    -U: Uninstall the project

    -c: Clean the project (remove all files)

    -i: Interactive mode (ask for the following options)
    -s: Silent mode (don't show prompts)

    -n: The hostname of the site (default: localhost)
    -p: The port of the site (default: 8080)
    -m: The folder to mount the database data (default: db_data)
    -d: The password for the database user (default: <random>)
    -r: The password for the database root user (default: <random>)

    -h: Show this help message

    The script will create a docker-compose.yml file and a .env file in the
    current directory. The .env file will contain the passwords for the database
    users as well as the hostname and port of the site. The docker-compose.yml
    file will contain the configuration for the wordpress site and the nginx
    reverse proxy. The script will also create a folder for the database data
    of the wordpress site.

    If the -I option is used, the script will:
        - Create the configuration files
        - Start the containers
        - Install the nginx reverse proxy configuration

    If the -C option is used, the script will:
        - Start Certbot to get a certificate for the domain

    If the -U option is used, the script will:
        - Stop the containers
        - Remove the containers
        - Uninstall the nginx reverse proxy configuration

    If the -c option is used, the script will:
        - Clean the project (remove all files)

    The script will check if the required programs are installed. Furthermore
    it will check if the DNS-Configuration is correct for the setup to work
    when requesting a certificate with Certbot.
```
