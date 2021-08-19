Discord
-------

**Enabling the Discord Plugin**

End-users can enable the Discord Plugin for a given Community by
initiating `Discord OAuth 2.0 Flow <https://discord.com/developers/docs/topics/oauth2>`_
through the ``/auth/discord/authorize`` endpoint.

Example request to authorize and enable Discord for a Metagov Community:

.. code-block::

    $METAGOV_SERVER/auth/discord/authorize?
        type=app
        &community=d4647d73-884a-44f5-af1a-7d7e87f87a90
        &redirect_uri=https%3A%2F%2Fpolicykit.metagov.org%2Fdiscord%2Finstall
        &state=randomstring

This will take the user through an authorization flow to install the Metagov app to a Discord guild.
On successful completion, the Discord Plugin is enabled for the provided Community, and a bot token is stored
and used to make all future requests.

**Logging in with Discord**

Example request to authorize a user:

.. code-block::

    $METAGOV_SERVER/auth/discord/authorize?
        type=user
        &redirect_uri=https%3A%2F%2Fpolicykit.metagov.org%2Fdiscord%2Flogin
        &state=randomstring
