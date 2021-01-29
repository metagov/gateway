from enum import Enum

# Based on http://martyalchin.com/2008/jan/10/simple-plugin-framework/

# plugins should import from this file
# plugins should not import from core


class ResourceRetrievalFunctionRegistry(object):
    def __init__(self):
        self.registry = dict()

    def get_function(self, name):
        return self.registry.get(name)

    def add(self, name, description, function):
        self.registry[name] = {
            'description': description,
            'function': function
        }


function_registry = ResourceRetrievalFunctionRegistry()


def retrieve_resource(name, description):
    """
    Decorator used by plugin authors writing resource retrieval functions.

    function input: querydict
    function output: HttpResponse
    """
    def decorate(func):
        function_registry.add(name, description, func)
        return func
    return decorate


class PluginMount(type):
    def __init__(cls, name, bases, attrs):
        if not hasattr(cls, 'plugins'):
            # This branch only executes when processing the mount point itself.
            # So, since this is a new plugin type, not an implementation, this
            # class shouldn't be registered as a plugin. Instead, it sets up a
            # dict where plugins can be registered later.
            cls.plugins = dict()
        else:
            # This must be a plugin implementation, which should be registered.
            cls.plugins[cls.slug] = cls


class GovernanceProcessProvider(metaclass=PluginMount):
    """
    Mount point for plugins which refer to governance processes that can be performed.
    Plugins implementing this reference should provide the following static functions:
    ========  ========================================================
    start     kick off the governance process
    cancel    cancel the governance process
    close     close the governance process
    ========  ========================================================
    """

    @staticmethod
    def start(job_state, querydict):
        # start process, update state
        # returns result
        pass

    @staticmethod
    def close(job_state, querydict):
        # close process, update state
        # returns outcome
        pass

    @staticmethod
    def cancel(job_state):
        # cancel job, update state
        pass

    @staticmethod
    def check(job_state):
        # check job status, update state if necessary (used for polling)
        # returns outcome
        pass

    @staticmethod
    def handle_webhook(job_state, querydict):
        # process data from webhook endpoint; update state if necessary
        pass


class GovernanceProcessStatus(Enum):
    CREATED = "CREATED"
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
