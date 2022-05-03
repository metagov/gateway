pipeline {
    agent any

    environment {
        current_branch=GIT_BRANCH.replace("origin/", "")
    }

    stages {
        stage("Creating Virtual Environment") {
            steps {
                script {
                    sh """
                    env
                    virtualenv venv
                    """
                }
            }
        }

        stage("Installing Requirements") {
            steps {
                script {
                    sh """
                    . venv/bin/activate
                    cd policykit
                    pip install -U pip setuptools
                    pip install -r requirements.txt
                    """
                }
            }
        }

        stage("Running Unit Test") {
            steps {
                script {
                    sh """
                    . venv/bin/activate
                    cd policykit
                    python manage.py test
                    """
                }
            }
        }
    }
}