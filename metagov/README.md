# Metagov Prototype

## Overview

The Metagov Prototype is a Django app with a plugin architecture. It is meant to be deployed alongside a "governance driver" such as PolicyKit.

See the [Metagov Prototype RFC](https://docs.google.com/document/d/1PQhIYQN_a3qBUCMc-OvX6oHyNB531nu32xeGV1OYv_w/edit#heading=h.kfc0oza24iyy) for an overview of the architecture and plugin interfaces.

### Governance Plugins

Plugins are located at [metagov/plugins](./metagov/plugins). Each plugin implements 1 or more of the following types of interfaces:

1. Resource retrieval (example: get SourceCred value for user X)
2. Asynchronous governance process (example: perform a vote on Loomio)
3. Listener/actor (TODO)
4. Widget (TODO)

### API endpoints

See the WIP auto-generated [Swagger API documentation](https://prototype.metagov.org/swagger/) for the Metagov Project's development instance. (Important: all the endpoints exposed under `/api/internal` are private and only accessible by the Driver on the local network. See deployment section for how to do this with Apache2.)

## Local Development

1. Fork and clone the repository
2. Navigate to the django project: `cd metagov-prototype/metagov`
3. Create Python3 virtual environment: `python3 -m venv env`
4. Activate the virtual environment: `source env/bin/activate`
5. Check pip for upgrades: `pip install --upgrade pip`
6. Install requirements: `pip install -r requirements.txt`
7. Set up an `.env` file for storing configs and secrets:
   ```
   cp metagov/.env.example metagov/.env
   DJANGO_SECRET_KEY=$(python manage.py shell -c 'from django.core.management import utils; print(utils.get_random_secret_key())')
   echo "DJANGO_SECRET_KEY=$DJANGO_SECRET_KEY" >> metagov/.env
   ```
8. _OPTIONAL_: set up a database, and point to it using `DATABASE_PATH` in `.env`. By default it will create a sqlite database at `metagov-prototype/metagov/db.sqlite3`.
9. Run existing migrations: `python manage.py migrate`
10. Start the server: `python manage.py runserver`

## Deployment

This has only been tested on Ubuntu 20.04.

### Setup

1. Add Metagov to the server by uploading the codebase or using `git clone`. Create a virtualenv and install all requirements into the virtualenv as above. For instructions, see [how to install python on ubuntu 20.0.4](https://www.digitalocean.com/community/tutorials/how-to-install-python-3-and-set-up-a-programming-environment-on-an-ubuntu-20-04-server).
2. Create the `.env` file as above, and update the values for `ALLOWED_HOSTS`, `DEBUG`, and `DATABASE_PATH`.
   > It is not recommended to keep the database inside the project directory, because you need to grant the apache2 user (`www-data`) access to the database its parent folder. Recommended: set the `DATABASE_PATH` to `/var/databases/metagov/db.sqlite3`, and make sure `www-data` has access write access to that directory.
3. Activate the virtual environment
4. Run `pip install -r requirements.txt`
5. Run `python manage.py migrate`
6. Run `python manage.py collectstatic`

### Deploy on Apache web server

Now that you have Metagov installed on your server, you can deploy it on Apache web server. Make sure you have a domain or subdomain dedicated to Metagov, that is pointing to your server's IP address.

1. Install apache2

   ```sh
   sudo apt-get install apache2 libapache2-mod-wsgi-py3
   ```

2. Create apache conf:
   ```sh
   cd /etc/apache2/sites-available
   cp default-ssl.conf mysite.com.conf #replace with your domain
   ```
3. Edit the config file. Below is an example-- make sure to replace the `ServerName` and paths as needed.

   ```aconf
   <IfModule mod_ssl.c>
           <VirtualHost _default_:443>
               ServerName prototype.metagov.org
               ServerAdmin webmaster@localhost
               Alias /static /metagov-prototype/metagov/static

               # 🚨 IMPORTANT: Restrict internal endpoints to local traffic
               <Location /api/internal>
                   Require local
               </Location>

               # Grant access to static files
               <Directory /metagov-prototype/metagov/static>
                       Require all granted
               </Directory>

               # Grant access to wsgi.py file
               <Directory /metagov-prototype/metagov/metagov>
                   <Files wsgi.py>
                           Require all granted
                   </Files>
               </Directory>

               WSGIDaemonProcess metagovssl python-home=/environments/metagov_env python-path=/metagov-prototype/metagov
               WSGIProcessGroup metagovssl
               WSGIScriptAlias / /metagov-prototype/metagov/metagov/wsgi.py

               # .. REST ELIDED
           </VirtualHost>
   </IfModule>
   ```

4. Test your config with `apache2ctl configtest`

5. Get an SSL certificate and set it up to auto-renew using LetsEncrypt. Follow step 4 here: [How To Secure Apache with Let's Encrypt on Ubuntu 20.04](https://www.digitalocean.com/community/tutorials/how-to-secure-apache-with-let-s-encrypt-on-ubuntu-20-04). Once that's done, add the newly created SSL files to your apache2 conf:
   ```aconf
   SSLCertificateFile /etc/letsencrypt/live/<YOUR SITE>/fullchain.pem
   SSLCertificateKeyFile /etc/letsencrypt/live/<YOUR SITE>/privkey.pem
   ```
6. Activate the site:
   ```sh
   a2ensite /etc/apache2/sites-available/mysite.com.conf
   ls /etc/apache2/sites-enabled/ #you should see a symlink to your site config here
   ```
7. Load your site in the browser!

   Check for errors at `/var/log/apache2/error.log` and `/var/log/django/debug.log` (or whatever logging path you have defined in `settings.py`). You may need to tweak permissions to make sure that the `www-data` user has access to what it needs.

8. Any time you update the code, you'll need to run `systemctl reload apache2` to reload the server.
