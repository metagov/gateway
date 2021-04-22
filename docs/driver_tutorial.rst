Driver Tutorial
===============
.. _drivertutorial-ref:
This tutorial will show you have to write a Driver that uses Metagov, or how to use Metagov
alongside your existing governance engine to turn it into a Driver.

Set up
^^^^^^
Deploy Metagov on the same machine as your Driver.
For local setup, follow the Metagov development setup docs (Coming soon!)


Single- or Multi-Community
^^^^^^^^^^^^^^^^^^^^^^^^^^^

The first thing to figure out is whether your Driver is going to support multiple Communities or a single Community.
A Community represents a group of people that use one or more online platforms.

If your Driver supports ONE community, just create it once with the desired plugins and configuration.

If your Driver supports MULTIPLE communities, you'll need to expose some way for community admins to create and configure Metagov communities.
Depending on which plugins are used, this process may include inputting API keys and registering webhooks in external systems.

To create or update a community, make a PUT request to the metagov ``/api/internal/community`` endpoint.
Each community is identified by a unique slug (``my-community-1234``):

.. code-block:: shell

    curl -X PUT 'http://127.0.0.1:8000/api/internal/community/my-community-1234' \
        -H 'Content-Type: application/json' \
        --data-raw '{
            "name": "my-community-1234",
            "readable_name": "",
            "plugins": [
                {
                    "name": "tutorial",
                    "config": {
                        "api_key": "ABC123",
                        "foo": "baz"
                    }
                }
            ]
        }'

Performing Actions
^^^^^^^^^^^^^^^^^^

Coming soon!

Performing asynchronous governance processes
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Coming soon!


Subscribing to Events
^^^^^^^^^^^^^^^^^^^^^

If you want your Driver to react to events occurring on other Platforms, you'll need to expose an
endpoint for receiving events from Metagov.

Set this setting in the metagov ``.env`` file:

.. code-block:: bash

    DRIVER_EVENT_RECEIVER_URL=<URL to event receiver endpoint>


When you activate a plugin that implements the "Listener" pattern (see the `Plugin Tutorial <plugintutorial-ref>`_),
you'll receive events as POST requests to your new endpoint. The event body will have this shape:

.. code-block:: JSON

    🚨 this shape is particularly unstable and will change!
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
