# Based on http://martyalchin.com/2008/jan/10/simple-plugin-framework/

class PluginMount(type):
    def __init__(cls, name, bases, attrs):
        if not hasattr(cls, 'plugins'):
            # This branch only executes when processing the mount point itself.
            # So, since this is a new plugin type, not an implementation, this
            # class shouldn't be registered as a plugin. Instead, it sets up a
            # list where plugins can be registered later.
            cls.plugins = []
        else:
            # This must be a plugin implementation, which should be registered.
            # Simply appending it to the list is all that's needed to keep
            # track of it later.
            cls.plugins.append(cls)
        
    def get_plugins(self,cls, *args, **kwargs):
        return [p(*args, **kwargs) for p in cls.plugins]

    def get_plugin_list(self,cls, *args, **kwargs):
        return cls.plugins

class ResourceProvider(metaclass=PluginMount):
    """
    Mount point for plugins which refer to actions that can be performed.
    Plugins implementing this reference should provide the following attributes:
    ========  ========================================================
    slug                 The slug to use for API route /resource/:slug
    retrieve_resource    function that should return the HttpResponse
    ========  ========================================================
    """

    # def __init__(self, request_input, *args, **kwargs):
        

    def retrieve_resource(self, input):
        """
        Retrieve a piece of data from an external system
        """


#### PLUGIN TYPES
# resource provider
# gov process
# listener/actor (can create PlatformActions)

#### PLUGIN POINTS
# API endpoint /retrieve-resources
# API endpoint /webhook/:plugin-key
# API endpoint /execute-platform-action
# API endpoint /governance-process
