Driver Tutorial
===============

This tutorial will show you have to write a governance Driver that uses Metagov, or how to use Metagov
alongside your existing governance engine.

You can also look at the `"Minimal Driver" Express App <https://github.com/metagov/example-driver>`_ for an example of a single-community Driver. (Warning! Example Driver may be out-of-sync with latest Metagov APIs. Copy-paste with caution.)

This tutorial assumes you are writing an **HTTP Driver**. A tutorial for Django Drivers is forthcoming.

Set up
------

You'll need to run Metagov on the same machine as your Driver.
Follow the instructions at :doc:`Metagov development setup <../development>`.


Single- or Multi-Community
--------------------------

The first thing to figure out is whether your Driver is going to support multiple Communities or a single Community.
A Community represents a group of people that use one or more online platforms.

If your Driver supports ONE community, just create it once with the desired plugins and configuration.

If your Driver supports MULTIPLE communities, you'll need to expose some way for community admins to create and configure Metagov communities.
Depending on which plugins are used, this process may include inputting API keys and registering webhooks in external systems.

To create or update a community, the Driver should make a PUT request to the Metagov community endpoint. Here's an example using CURL:

.. code-block:: shell

    curl -X PUT 'http://127.0.0.1:8000/api/internal/community/my-community-1234' \
        -H 'Content-Type: application/json' \
        --data-raw '{
            "name": "my-community-1234",
            "readable_name": "",
            "plugins": [
                {
                    "name": "sourcecred",
                    "config": {
                        "server_url": "https://metagov.github.io/sourcecred-instance"
                    }
                }
            ]
        }'

The response code will be ``201`` if the community was successfully created, or ``200`` if the community was successfully updated.
Each community is identified by a unique slug (in this example, it's ``my-community-1234``).
When making subsequent Metagov requests to perform actions or processes, the Driver must include the community slug in the ``X-Metagov-Community`` header.

Plugin Configuration and Webhooks
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Some Plugins, such as Loomio, Discourse, and Open Collective, require webhooks to be configured in the external platform.
Metagov exposes one webhook receiver endpoint *per-Plugin-per-Community*.
Metagov webhook receiver endpoints have the format: ``/api/hooks/<community>/<plugin>[/<webhook_slug>]``.

The Driver can retrieve a list of available webhook receivers for a given community by making a request like this:

.. code-block:: shell

    # 🚨  Highly experimental, this will change soon

    # request
    curl -X GET 'http://127.0.0.1:8000/api/internal/community/my-community-1234/hooks'

    # response
    HTTP/1.1 200 OK
    {
        "hooks": [
            "/api/hooks/my-community-1234/loomio/f5c3ff8f",  # Optional "webhook_slug" config used, for security
            "/api/hooks/my-community-1234/discourse",        # No webhook slug, because Discourse supports webhook secrets
            "/api/hooks/my-community-1234/randomness         # Generated even though the plugin doesn't use it
        ]
    }

If you're creating a **Multi-Community Drivers**, you'll need to instruct the user to set up these webhooks in each service.
The user will typically need to be an admin on each platform (Discourse, OpenCollective, etc) in order to register the unique webhook.


Performing Actions
------------------

The Driver can perform an action by making a request to the Metagov API at ``/api/internal/action/<plugin>.<action>``.

The available actions, along with their input and output types, are listed in the API docs.
You can find those at ``/swagger`` or ``/redoc`` of your Metagov instance. Or, take a look at the
`dev instance Metagov API docs <https://metagov.policykit.org/redoc/>`_.

Here's an example of an API request to perform the action ``sourcecred.user-cred`` for the ``my-community-1234`` community:

.. code-block:: shell

    # request
    curl -X POST 'http://127.0.0.1:8000/api/internal/action/sourcecred.user-cred' \
        -H 'X-Metagov-Community: my-community-1234' \
        -H 'Content-Type: application/json' \
        --data-raw '{
            "parameters": {
                "username": "system"
            }
        }'

    # response
    HTTP/1.1 200 OK
    {"value": 0.008520052699137347}

The shape of the response body is defined by the SourceCred plugin.
The request will fail if the ``sourcecred`` plugin is not enabled for the community ``my-community-1234``.


Performing Governance Processes
-------------------------------------

A Governance Process is a decision-making process, such as a vote, election, or budgeting process.
This process typically involves some engagement from community members, and can last anywhere from minutes to hours to weeks.

The currently supported governance processes are listed in the API docs, which can be found at ``/swagger`` or ``/redoc`` on your Metagov instance.
Or, take a look at the `dev instance Metagov API docs <https://metagov.policykit.org/redoc/>`_.

The governance process endpoints use a typical asynchronous request-reply pattern with callbacks.
Here's an example CURL request that kicks off a ``loomio.poll`` process:

.. code-block:: shell
    :emphasize-lines: 6

    # request
    curl -i -X POST 'http://127.0.0.1:8000/api/internal/process/loomio.poll' \
        -H 'X-Metagov-Community: my-community-1234' \
        -H 'Content-Type: application/json' \
        --data-raw '{
            "callback_url": "https://mydriver.org/receive-outcome/4",
            "title": "the title of the poll",
            "options": ["one", "two", "three"],
            "closing_at": "2022-01-01"
        }'

    # response
    HTTP/1.1 202 Accepted
    Location: /api/internal/process/loomio.poll/127   # <-- location of the process


The ``callback_url`` parameter is special. When the process completes, or when the outcome is changed (for example a vote is cast), Metagov will make a POST request
to the callback URL with the process record.

After kicking off a process, make a ``GET`` request to the URL from the ``Location`` header to get initial information about the process:

.. code-block:: shell

    # request
    curl -i -X GET 'http://127.0.0.1:8000/api/internal/process/loomio.poll/127'

    # response
    HTTP/1.1 200 OK
    {
        "id": 127,
        "name": "loomio.poll",
        "community": "my-community-1234",
        "status": "pending",
        "errors": {},
        "outcome": {   # <-- the shape of this object will differ for each process
            "poll_url": "https://www.loomio.org/p/1234",
            "votes": {"one": 1, "two": 0, "three": 0}
        }
    }

If the plugin supports it, the Driver can "close" the process early by making a ``DELETE`` request to the same location:

.. code-block:: shell

    # request
    curl -i -X DELETE 'http://127.0.0.1:8000/api/internal/process/discourse.poll/127'

    # response
    HTTP/1.1 200 OK

    {
        "id": 128,
        "name": "discourse.poll",
        "community": "my-community-1234",
        "status": "completed",
        "errors": {},
        "outcome": {
            "poll_url": "https://www.loomio.org/p/1234",
            "votes": {"one": 1, "two": 2, "three": 4}
        }
    }


Subscribing to Events
---------------------

If you want your Driver to react to events occurring on other Platforms, you'll need to expose an
endpoint for receiving events from Metagov.

Set this setting in the metagov ``.env`` file:

.. code-block:: bash

    DRIVER_EVENT_RECEIVER_URL=<URL to event receiver endpoint>


When you activate a plugin that implements the "Listener" pattern (see the :doc:`Plugin Tutorial <../plugin_tutorial>`),
you'll receive events as POST requests to your new endpoint. The event body will have this shape:

.. code-block::

    # 🚨 this shape is particularly unstable and will change!
    {
        "community": "my-community-123",     # unique community slug
        "source": "discourse",               # name of the plugin that is emitting this event
        "event_type": "post_created",        # event type
        "timestamp": "1619102376.5358589",   # time that the event was sent (time in seconds since the epoch as a floating point number)
        "data": {...}                        # data about the event, can have any shape
        "initiator": {                       # the user that initiated the event (optional)
            "user_id": "alice",              # user identifier that is unique to the identity provider
            "provider": "discourse"          # key for the identity provider
        }
    }

