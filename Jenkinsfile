pipeline {
    agent any

    environment {
        downstream_job_name = 'Policykit CICD'
        working_directory="${WORKSPACE}/metagov"
        current_branch=GIT_BRANCH.replace("origin/", "")
        DJANGO_SECRET_KEY='t5y0(1hpfj2%%qrys%rjso*dfb6ph%3t2dmag=+9o%t(=l3w#9'
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
                    cd "${env.working_directory}"
                    pip3 install -U pip setuptools
                    pip3 install -r requirements.txt
                    """
                }
            }
        }

        stage("Running Unit Test") {
            steps {
                script {
                    sh """
                    . venv/bin/activate
                    cd "${env.working_directory}"
                    python3 manage.py test
                    """
                }
            }
        }
    }

    post {
        always {
            cleanWs()
            script {
                owner_repo = GIT_URL.replaceAll("https://github.com/", "").replaceAll(".git", "")

                if (env.CHANGE_URL) {
                    commit_type = "PR"
                    html_url = env.CHANGE_URL
                    pr_api = CHANGE_URL.replaceAll("https://github.com/", "https://api.github.com/repos/").replaceAll("pull", "pulls")
                    def commit_sha = sh(script: "curl -H 'Accept: application/vnd.github.v3+json' ${pr_api} | jq -r .base.sha", returnStdout: true).trim()
                    api_url = "https://api.github.com/repos/${owner_repo}/commits/${commit_sha}"
                }
                else {
                    commit_type = "Commit"
                    html_url = "https://github.com/${owner_repo}/commit/${GIT_COMMIT}"
                    api_url = "https://api.github.com/repos/${owner_repo}/commits/${GIT_COMMIT}"
                }

                def commit_metadata = sh(script: "curl -H 'Accept: application/vnd.github.v3+json' ${api_url} | jq .commit", returnStdout: true).trim()
                def commit_metadata_json = readJSON text: commit_metadata

                commit_message = "${commit_metadata_json.message}"
                committer_name  = "${commit_metadata_json.committer.name}"
                committer_email  = "${commit_metadata_json.committer.email}"
            }
        }

        success {
            script {
                 slackSend botUser: true,
                           color: '#00ff00',
                           message: "Type: " + commit_type +
                                    "\n User: " + committer_name +
                                    "\n Branch: " + GIT_BRANCH +
                                    "\n Message: " + commit_message +
                                    "\n Build Status: Passed :tada: :tada: :tada:" +
                                    "\n Build Url: " + BUILD_URL +
                                    "\n Github Url: " + html_url

                build job: env.downstream_job_name,
                wait: true
            }
        }

        failure {
            script {
                slackSend botUser: true,
                      color: '#ff0000',
                      message: "Type: " + commit_type +
                               "\n User: " + committer_name +
                               "\n Branch: " + GIT_BRANCH +
                               "\n Message: " + commit_message +
                               "\n Build Status: Failed :disappointed: :disappointed: :disappointed:" +
                               "\n Build Url: " + BUILD_URL +
                               "\n Github Url: " + html_url
            }
        }
    }
}