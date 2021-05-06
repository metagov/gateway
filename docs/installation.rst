Installing Metagov
==================

Metagov needs to be installed on the same server as your governance "Driver":

* If you're using PolicyKit as your Driver, head over to the `PolicyKit Documentation <https://policykit.readthedocs.io/>`_ for instructions on how to install PolicyKit on your server.
* If you're using Metagov alongside your existing system, just make sure that you're installing Metagov on the same machine. This is necessary because Metagov and your system will communicate over the local network.

Follow these isntructions to set up Metagov on your Ubuntu server.
We’ll assume that you don’t have Python or apache2 installed on your Ubuntu system.
These installation instructions have only been tested on **Ubuntu 20.04**.

Clone Metagov
^^^^^^^^^^^^^

Clone the Metagov repository (or your fork):

.. code-block:: shell

    git clone https://github.com/metagov/metagov-prototype.git


Install Dependencies
^^^^^^^^^^^^^^^^^^^^

Install Python3, and create and activate a new virtual environment by following
this tutorial from Digital Ocean: `how to install python on ubuntu 20.0.4 <https://www.digitalocean.com/community/tutorials/how-to-install-python-3-and-set-up-a-programming-environment-on-an-ubuntu-20-04-server>`_.

Next, install the Metagov requirements:

.. code-block:: shell

    pip install --upgrade pip
    pip install -r requirements.txt

Set up the Metagov Environment
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Set up an ``.env`` file for storing secrets, and generate a new DJANGO_SECRET_KEY:

.. code-block:: shell

    cp metagov/.env.example metagov/.env
    DJANGO_SECRET_KEY=$(python manage.py shell -c 'from django.core.management import utils; print(utils.get_random_secret_key())')
    echo "DJANGO_SECRET_KEY=$DJANGO_SECRET_KEY" >> metagov/.env

Next, open up your ``.env`` file and set the following values:

.. code-block:: shell

    ALLOWED_HOSTS=<your host>
    DATABASE_PATH=<your database path>


Make sure that your database path is _not_ inside the Metagov repository directory, because you need to grant the apache2 user (``www-data``) access to the database its parent folder. Recommended: set the ``DATABASE_PATH`` to ``/var/databases/metagov/db.sqlite3``, and make sure ``www-data`` has access write access to that directory.

Set up the Database
^^^^^^^^^^^^^^^^^^^

Run ``python manage.py migrate`` to set up your database.

To test that everything is working correctly, enter the Django shell:

.. code-block:: shell

    python manage.py shell_plus

Deploy with Apache web server
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Now that you have Metagov installed on your server, you can deploy it on Apache web server.
Make sure you have a domain or subdomain dedicated to Metagov, that is pointing to your server's IP address.


1. Install apache2

   .. code-block:: shell

        sudo apt-get install apache2 libapache2-mod-wsgi-py3

2. Create apache conf:

   .. code-block:: shell
   
        cd /etc/apache2/sites-available
        cp default-ssl.conf SERVER_NAME.conf

3. Edit the config file to look like this:


    .. code-block:: aconf

        <IfModule mod_ssl.c>
                <VirtualHost _default_:443>
                    ServerName $SERVER_NAME
                    ServerAdmin webmaster@localhost
                    Alias /static $METAGOV_REPO/metagov/static

                    # 🚨 IMPORTANT: Restrict internal endpoints to local traffic 🚨
                    <Location /api/internal>
                        Require local
                    </Location>

                    # Grant access to static files for the API docs.
                    <Directory $METAGOV_REPO/metagov/static>
                            Require all granted
                    </Directory>

                    # Grant access to wsgi.py file. This is the Django server.
                    <Directory $METAGOV_REPO/metagov/metagov>
                        <Files wsgi.py>
                                Require all granted
                        </Files>
                    </Directory>

                    WSGIDaemonProcess metagovssl python-home=$METAGOV_ENV python-path=$METAGOV_REPO/metagov
                    WSGIProcessGroup metagovssl
                    WSGIScriptAlias / $METAGOV_REPO/metagov/metagov/wsgi.py

                    # .. REST ELIDED
                </VirtualHost>
        </IfModule>

4. Test your config with ``apache2ctl configtest``

5. Get an SSL certificate and set it up to auto-renew using LetsEncrypt. Follow step 4 here: `How To Secure Apache with Let's Encrypt on Ubuntu 20.04 <https://www.digitalocean.com/community/tutorials/how-to-secure-apache-with-let-s-encrypt-on-ubuntu-20-04>`_. Once that's done, add the newly created SSL files to your apache2 conf:

    .. code-block:: aconf

        SSLCertificateFile /etc/letsencrypt/live/$SERVER_NAME/fullchain.pem
        SSLCertificateKeyFile /etc/letsencrypt/live/$SERVER_NAME/privkey.pem

6. Activate the site:

   .. code-block:: shell

        a2ensite /etc/apache2/sites-available/$SERVER_NAME.conf
        ls /etc/apache2/sites-enabled/ # you should see a symlink to your site config here

7. Load your site in the browser.

   Check for errors at ``/var/log/apache2/error.log`` and ``/var/log/django/debug.log`` (or whatever logging path you have defined in ``settings.py``). The ``www-data`` user should own the Django log directory and have write-access to the log file.

8. Any time you update the code, you'll need to run ``systemctl reload apache2`` to reload the server.

Set up Celery
^^^^^^^^^^^^^^^

Metagov uses Celery to run scheduled tasks for Governance Processes and Plugin listeners.
Follow these instructions to daemonize celery on your machine.
For more information about Celery configuration options, see the `Celery docs <https://docs.celeryproject.org/en/stable/userguide/daemonizing.html>`_.

Create RabbitMQ virtual host
""""""""""""""""""""""""""""

Install RabbitMQ:

.. code-block:: shell

    sudo apt-get install rabbitmq-server

Follow these instruction to `create a RabbitMQ username, password, and virtual host <https://docs.celeryproject.org/en/stable/getting-started/brokers/rabbitmq.html#setting-up-rabbitmq>`_.

In ``metagov/settings.py``, set the ``CELERY_BROKER_URL`` as follows, substituting values for your RabbitMQ username, password, and virtual host:

.. code-block:: python

    CELERY_BROKER_URL = "amqp://USERNAME:PASSWORD@localhost:5672/VIRTUALHOST"


Create celery user
""""""""""""""""""""""

If you don't already have a ``celery`` user, create one:

.. code-block:: bash

    sudo useradd celery -d /home/celery -b /bin/bash

Give the ``celery`` user access to necessary pid and log folders:

.. code-block:: bash

    sudo useradd celery -d /home/celery -b /bin/bash
    sudo mkdir /var/log/celery
    sudo chown -R celery:celery /var/log/celery
    sudo chmod -R 755 /var/log/celery
    
    sudo mkdir /var/run/celery
    sudo chown -R celery:celery /var/run/celery
    sudo chmod -R 755 /var/run/celery

The ``celery`` user will also need write-access to the Django log files.
The ``www-data`` user (Apache2) should own the log directory.
To give ``celery`` access, create a group that contains both ``www-data`` and ``celery``.
For example, if your Django logs are in ``/var/log/django``:

.. code-block:: bash

    sudo groupadd www-and-celery
    sudo usermod -a -G www-and-celery celery
    sudo usermod -a -G www-and-celery www-data
    sudo chgrp -R www-and-celery /var/log/django
    sudo chmod -R 770 /var/log/django

Create Celery configuration files
"""""""""""""""""""""""""""""""""

Next, you'll need to create three Celery configuration files for Metagov.

Using Metagov with PolicyKit? These configuration files are designed specifically to work with the setup where PolicyKit and Metagov are deployed together.
PolicyKit will use separate ``celery`` and ``celerybeat`` services. Just make sure that PolicyKit is using a different RabbitMQ virtual host as the ``CELERY_BROKER_URL``.

.. note::

    In the remaining configuration examples, make sure to substitute the following values:

    ``$METAGOV_REPO`` is the path to your metagov-prototype repository root.
    
    ``$METAGOV_ENV`` is the path to your metagov virtual environment.
    
    ``$SERVER_NAME`` is  your server name.

``/etc/conf.d/celery-metagov``
""""""""""""""""""""""""""""""

.. code-block:: bash

    CELERYD_NODES="mg1"

    # Absolute or relative path to the 'celery' command:
    CELERY_BIN="$METAGOV_ENV/bin/celery"

    # App instance to use
    CELERY_APP="metagov"

    # How to call manage.py
    CELERYD_MULTI="multi"

    # Extra command-line arguments to the worker
    CELERYD_OPTS="--time-limit=300 --concurrency=4"

    # - %n will be replaced with the first part of the nodename.
    # - %I will be replaced with the current child process index
    #   and is important when using the prefork pool to avoid race conditions.
    CELERYD_PID_FILE="/var/run/celery/%n.pid"
    CELERYD_LOG_FILE="/var/log/celery/%n%I.log"
    CELERYD_LOG_LEVEL="INFO"

    # you may wish to add these options for Celery Beat
    CELERYBEAT_PID_FILE="/var/run/celery/metagov_beat.pid"
    CELERYBEAT_LOG_FILE="/var/log/celery/metagov_beat.log"

``/etc/systemd/system/celery-metagov.service``
""""""""""""""""""""""""""""""""""""""""""""""

.. code-block:: bash

    [Unit]
    Description=Celery Service
    After=network.target

    [Service]
    Type=forking
    User=root
    Group=root
    EnvironmentFile=/etc/conf.d/celery-metagov
    WorkingDirectory=$METAGOV_REPO/metagov
    ExecStart=/bin/sh -c '${CELERY_BIN} multi start ${CELERYD_NODES} \
    -A ${CELERY_APP} --pidfile=${CELERYD_PID_FILE} \
    --logfile=${CELERYD_LOG_FILE} --loglevel=${CELERYD_LOG_LEVEL} ${CELERYD_OPTS}'
    ExecStop=/bin/sh -c '${CELERY_BIN} multi stopwait ${CELERYD_NODES} \
    --pidfile=${CELERYD_PID_FILE}'
    ExecReload=/bin/sh -c '${CELERY_BIN} multi restart ${CELERYD_NODES} \
    -A ${CELERY_APP} --pidfile=${CELERYD_PID_FILE} \
    --logfile=${CELERYD_LOG_FILE} --loglevel=${CELERYD_LOG_LEVEL} ${CELERYD_OPTS}'

    [Install]
    WantedBy=multi-user.target


``/etc/systemd/system/celerybeat-metagov.service``
""""""""""""""""""""""""""""""""""""""""""""""""""

.. code-block:: bash

    [Unit]
    Description=Celery Beat Service
    After=network.target

    [Service]
    Type=simple
    User=root
    Group=root
    EnvironmentFile=/etc/conf.d/celery-metagov
    WorkingDirectory=$METAGOV_REPO/metagov
    ExecStart=/bin/sh -c '${CELERY_BIN} -A ${CELERY_APP}  \
    beat --pidfile=${CELERYBEAT_PID_FILE} \
    --logfile=${CELERYBEAT_LOG_FILE} --loglevel=${CELERYD_LOG_LEVEL} --schedule=/var/run/celery/celerybeat-metagov-schedule'

    [Install]
    WantedBy=multi-user.target

Start Celery services
"""""""""""""""""""""

.. code-block:: shell
    
    # Run this after creating or changing the above 3 config files
    systemctl daemon-reload

    # Start celery and celerybeat services
    systemctl start celery-metagov celerybeat-metagov

    # Check status of all celery services
    systemctl status 'celery*'
    systemctl list-units | grep celery

    # Inspect celery metagov logs
    less /var/log/celery/mg1.log          # logs from the worker
    less /var/log/celery/metagov_beat.log # logs from celerybeat
    less /var/log/django/metagov.log      # tasks should log to metagov's normal file handler

    # Restart celery. You'll need to do this whenever the task code changes.
    systemctl restart celery-metagov

