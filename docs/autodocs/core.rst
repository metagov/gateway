Autodocumentation
=================

Models
######

Plugin authors implement `Proxy Models <https://docs.djangoproject.com/en/3.1/topics/db/models/#proxy-models>`_ and decorate them with :ref:`Class Decorators`.

.. autoclass:: metagov.core.models.Plugin
    :members:
    :exclude-members: save, DoesNotExist, MultipleObjectsReturned
|
.. autoclass:: metagov.core.models.GovernanceProcess
    :members:
    :exclude-members: DoesNotExist, MultipleObjectsReturned
|
Decorators
##########
Add decorators to register classes and functions with metagov core.

Class Decorators
****************

.. autofunction:: metagov.core.plugin_decorators.plugin
.. autofunction:: metagov.core.plugin_decorators.governance_process

Function Decorators
*******************

.. autofunction:: metagov.core.plugin_decorators.resource
.. autofunction:: metagov.core.plugin_decorators.action