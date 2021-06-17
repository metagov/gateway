Slack
-----

**Enabling the Slack Plugin**

End-users can enable the Slack Plugin for a given Community by
initiating `Slack OAuth 2.0 Flow <https://api.slack.com/authentication/oauth-v2>`_ 
through the ``/auth/slack/authorize`` endpoint.

Example request to authorize and enable Slack for a Metagov Community:

.. code-block::

    $METAGOV_SERVER/auth/slack/authorize?
        type=app
        &community=d4647d73-884a-44f5-af1a-7d7e87f87a90
        &redirect_uri=https%3A%2F%2Fpolicykit.metagov.org%2Fslack%2Finstall
        &state=randomstring

This will take the user through an authorization flow to install the Metagov app to a Slack workspace.
On successful completion, the Slack Plugin is enabled for the provided Community, and a bot token is stored
and used to make all future requests.

**Logging in with Slack**

Example request to authorize a user:

.. code-block::

    $METAGOV_SERVER/auth/slack/authorize?
        type=user
        &redirect_uri=https%3A%2F%2Fpolicykit.metagov.org%2Fslack%2Flogin
        &state=randomstring
