Local Development
=================

Follow these instructions to setup Metagov for local development.
You'll want to do this if you are developing a Metagov Plugin,
developing Metagov Core, or developing a Driver locally.
If you're ready to install Metagov to your Ubuntu server,
head over to `Installing Metagov <../installation>`_ instead.

1. Clone the Metagov repository (or your fork):

    .. code-block:: shell

        git clone https://github.com/metagov/metagov-prototype.git

2. Navigate to the django project

    .. code-block:: shell

        cd metagov-prototype/metagov

3. Create and activate a Python3 virtual environment:

    .. code-block:: shell

        python3 -m venv env
        source env/bin/activate

4. Install requirements:

    .. code-block:: shell

        pip install --upgrade pip
        pip install -r requirements.txt


5. Set up an ``.env`` file for storing secrets, and generate a new DJANGO_SECRET_KEY:

    .. code-block:: shell

        cp metagov/.env.example metagov/.env
        DJANGO_SECRET_KEY=$(python manage.py shell -c 'from django.core.management import utils; print(utils.get_random_secret_key())')
        echo "DJANGO_SECRET_KEY=$DJANGO_SECRET_KEY" >> metagov/.env

8. (OPTIONAL) Set up a database, and point to it using ``DATABASE_PATH`` in the ``.env`` file. By default, Django will create a sqlite database at ``metagov-prototype/metagov/db.sqlite3``.

9. Run existing migrations:

    .. code-block:: shell

        python manage.py migrate

10. Start the server:

    .. code-block:: shell

        python manage.py runserver

Bonus steps:

11. Run tests:

    .. code-block:: shell

        python manage.py test

11. Access the Django shell:

    .. code-block:: shell

        python manage.py shell_plus

