import logging
import random

import metagov.core.plugin_decorators as Registry
import metagov.plugins.revshare.schemas as Schemas
from metagov.core.errors import PluginErrorInternal
from metagov.core.models import Plugin

logger = logging.getLogger(__name__)

DEFAULT_KEY = "_DEFAULT"

@Registry.plugin
class RevShare(Plugin):
    name = "revshare"

    class Meta:
        proxy = True

    def initialize(self):
        # This state only lasts as long as the plugin does.
        # If the community decides to de-activates the plugin, the plugin instance is deleted and the state is lost.
        self.state.set(DEFAULT_KEY, {})

    @Registry.action(
        slug="add-pointer",
        description="Add weighted pointer to revshare config, or update its weight if it already exists",
        input_schema=Schemas.add_pointer_input,
    )
    def add_pointer(self, parameters):
        pointer = parameters["pointer"]
        weight = parameters["weight"]
        key = parameters.get("key", DEFAULT_KEY)
        config = self.state.get(key) or {}
        config[pointer] = weight
        self.state.set(key, config)
        return config

    @Registry.action(
        slug="remove-pointer",
        description="Remove pointer from revshare config",
        input_schema=Schemas.remove_pointer_input
    )
    def remove_pointer(self, parameters):
        pointer = parameters["pointer"]
        key = parameters.get("key", DEFAULT_KEY)
        config = self.state.get(key) or {}
        config.pop(pointer, None)
        self.state.set(key, config)
        return config

    @Registry.action(
        slug="replace-config",
        description="Replace revshare config with new config",
        input_schema=Schemas.replace_config_input,
    )
    def replace(self, parameters):
        new_pointers = parameters["pointers"]
        key = parameters.get("key", DEFAULT_KEY)
        self.state.set(key, new_pointers)
        return new_pointers

    @Registry.action(
        slug="get-config",
        description="Get current revshare configuration",
        input_schema=Schemas.get_config_input,
        is_public=True,
    )
    def get_config(self, parameters):
        key = parameters.get("key", DEFAULT_KEY)
        return self.state.get(key) or {}

    @Registry.action(
        slug="pick-pointer",
        description="Choose a random pointer according to weights",
        input_schema=Schemas.pick_pointer_input,
        output_schema=Schemas.pick_pointer_output,
        is_public=True,
    )
    def pick_pointer(self, parameters):
        key = parameters.get("key", DEFAULT_KEY)
        pointers = self.state.get(key) or {}
        if len(pointers) == 0:
            raise PluginErrorInternal(f"No pointers for key {key}")
        # based on https://webmonetization.org/docs/probabilistic-rev-sharing/
        sum_ = sum(list(pointers.values()))
        choice = random.random() * sum_
        for (pointer, weight) in pointers.items():
            choice = choice - weight
            if choice <= 0:
                return {"pointer": pointer}
