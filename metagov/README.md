# Metagov Prototype

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
8. *OPTIONAL*: set up a database, and point to it using `DATABASE_PATH` in `.env`. By default it will create a sqlite database at `metagov-prototype/metagov/db.sqlite3`.
9. Run existing migrations: `python manage.py migrate`
10. Start the server: `python manage.py runserver`
