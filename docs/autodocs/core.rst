Reference Documentation
=======================

Models
######

Plugin authors implement `Proxy Models <https://docs.djangoproject.com/en/3.1/topics/db/models/#proxy-models>`_ and decorate them with :ref:`Class Decorators`.

.. autoclass:: metagov.core.models.Community
    :members:
    :exclude-members: DoesNotExist, MultipleObjectsReturned

|

.. autoclass:: metagov.core.models.Plugin
    :members:
    :exclude-members: save, DoesNotExist, MultipleObjectsReturned

|

.. autoclass:: metagov.core.models.GovernanceProcess
    :members:
    :exclude-members: save, DoesNotExist, MultipleObjectsReturned

|



Decorators
##########
Add decorators to register classes and functions with metagov core.

Class Decorators
****************

.. autofunction:: metagov.core.plugin_manager.Registry.plugin
.. autofunction:: metagov.core.plugin_manager.Registry.governance_process

Function Decorators
*******************

.. autofunction:: metagov.core.plugin_manager.Registry.action
.. autofunction:: metagov.core.plugin_manager.Registry.event_producer_task
.. autofunction:: metagov.core.plugin_manager.Registry.webhook_receiver
