Design Overview
===============

Metagov is a Django backend service with a plugin architecture. Metagov is meant to be deployed alongside a governance :ref:`Driver`, where the specific governance decisions are made. Drivers written in Django can import the Metagov Django app directly. Drivers written with other frameworks or using other languages will need to communicate with Metagov via HTTP. Both kinds of drivers use Metagov to communicate with zero or more third party services.

Metagov has a plugin architecture, with nearly all the functionality being defined in the plugins. Plugins are typically used to integrate with an external platform such as SourceCred or Loomio, and expose their governance-related functionality through a common interface that can be consumed by the Driver.

.. image:: _static/20210408_diagram_driver_metagov.png
   :width: 600


API Access
--------------------------

All drivers (that is, both Django and HTTP Drivers) make use of the API endpoints provided by Metagov to communicate with third-party platforms. These public endpoints allow platforms like Slack, Github, etc, to notify Metagov (and therefore the driver) when actions happen on those platforms.

Additionally, HTTP Drivers must use the API to access Metagov's other functionality (whereas Django Drivers can directly import and call functions, models, etc). To enable this, a separate app called HTTPWrapper wraps Metagov's functionality into HTTP endpoints. To access these endpoints, Drivers need to make Driver Accounts on a local or hosted system and then authenticate to those endpoints.

.. WARNING::

    The functionality described in this section is in development. Please reach out for help when working in this area.


.. list-table:: Metagov APIs
   :widths: 40 21 39
   :header-rows: 1

   * - Metagov URL
     - Used By
     - Description
   * - ``/api/hooks/<community>/<plugin>``
     - ALL
     - Receive incoming events from external platforms (Open Collective, Loomio, etc)
   * - ``/api/internal/community/<community>``
     - HTTP DRIVERS
     - Create/update/delete a community
   * - ``/api/action/<plugin>.<action>``
     - HTTP DRIVERS
     - Perform an action configured by the plugin author
   * - ``/api/internal/process/<plugin>.<process>``
     - HTTP DRIVERS
     - Perform an asynchronous governance process

Driver
------

The Driver implements a governance engine of some kind. It may allow people to author governance policies, and implement the ability to incorporate the processes, listeners, and resources defined by Metagov plugins into governance policies. It’s up to the driver whether they can do this abstractly (so they can handle any Metagov plugin) or whether they need to painstakingly do this one by one and so only work with some plugins.

As explained above, Drivers communicate with Metagov in one of two ways. A Django-based Driver may choose to import Metagov as an app and call its functions and models directly. A non-Django Driver will need to communicate with Metagov over HTTP. We call these types of drivers Django Drivers and HTTP Drivers respectively.

The Driver might be capable of supporting multiple communities or only one community. The Driver is responsible for configuring the community(ies) in Metagov by making a request to Metagov's ``/community`` endpoint or by directly creating the community via Django models. After that, any time the Driver makes a community-specific request to Metagov, it must include the unique community name in the header ``X-Metagov-Community`` (HTTP Driver) or supply it as a parameter (Django Driver).

The Driver may also react to event notifications that it receives from Metagov, which could in turn trigger a policy evaluation.

For a minimal example of a driver, see the repo `metagov/example-driver <https://github.com/metagov/example-driver>`_.


Communities
-----------

A Community represents a group of people that use one or more online platforms together. A community can activate and configure metagov plugins to use them for governance.

An HTTP :ref:`Driver` can create or update a community by making a ``PUT`` request to the ``/community`` endpoint. Here's an example of a JSON-serialized community that has the ``sourcecred`` plugin enabled:

.. code-block:: json

   {
      "name": "metagov-project-community",
      "readable_name": "The Metagovernance Project",
      "plugins": [
         {
            "name": "sourcecred",
            "config": {
               "server_url": "https://metagov.github.io/sourcecred-instance"
            }
         }
      ]
   }


Metagov Core
------------

The Metagov core is responsible for:

* Managing plugins and exposing their functionality to the Driver.
* Sending event notifications from Plugins to the Driver.
* Exposing endpoints for receiving webhook events from external platforms, and routing hooks to the correct plugin.

Metagov Plugins
---------------

Developers can create Plugins to connect to governance services and platforms.
Plugins are defined as proxy subclasses of the Plugin model.
Plugin authors define governance processes and actions on the model, and Metagov exposes them to the Driver.
See :doc:`Plugin Tutorial <../plugin_tutorial>`.

Django Data Model
-----------------

Metagov Core defines three Django models: ``Community``, ``Plugin``, and ``GovernanceProcess``.

The ``GovernanceProcess -> Plugin`` relationship is many-to-one. A single Loomio model can have multiple LoomioPoll processes going at once.

The ``Plugin -> Community`` relationship is many-to-one. A single Community can have several of Plugins activated. Currently it can only have one instance `per proxy type` (one community can't have two instances of Loomio, for example).

See the :doc:`Reference Documentation <../autodocs/core>` for reference.

.. image:: _static/20210324_django_schema_graph.png
   :width: 800
