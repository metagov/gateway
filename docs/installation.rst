Installing Metagov
==================

Metagov needs to be installed on the same server as your governance "Driver":

* If you're using PolicyKit as your Driver, head over to the `PolicyKit Documentation <https://policykit.readthedocs.io/>`_ for instructions on how to install PolicyKit on your server.
* If you're using Metagov alongside your existing system, just make sure that you're installing Metagov on the same machine. This is necessary because Metagov and your system will communicate over the local network.

Follow these isntructions to set up Metagov on your Ubuntu server.
We’ll assume that you don’t have Python or apache2 installed on your Ubuntu system.

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

Set up Metagov Environment
^^^^^^^^^^^^^^^^^^^^^^^^^^

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

Set up Database
^^^^^^^^^^^^^^^^^^^^^^^^^^

Run ``python manage.py migrate`` to set up your database.

To test that everything is working correctly, enter the Django shell:

.. code-block:: shell

    python manage.py shell_plus

Deploy with Apache web server
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Now that you have Metagov installed on your server, you can deploy it on Apache web server.
Make sure you have a domain or subdomain dedicated to Metagov, that is pointing to your server's IP address.

In the following examples, make sure to substitue the following values:

Replace ``$METAGOV_REPO`` with the path to your metagov-prototype repository root.

Replace ``$METAGOV_ENV`` with the path to your metagov virtual environment.

Replace ``$SERVER_NAME`` with your server name.

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

   Check for errors at ``/var/log/apache2/error.log`` and ``/var/log/django/debug.log`` (or whatever logging path you have defined in ``settings.py``). You may need to tweak permissions to make sure that the ``www-data`` user has access to what it needs.

8. Any time you update the code, you'll need to run ``systemctl reload apache2`` to reload the server.
