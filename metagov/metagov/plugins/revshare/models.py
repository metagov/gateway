import json
import logging
import random

import metagov.core.plugin_decorators as Registry
import metagov.plugins.revshare.schemas as Schemas
from metagov.core.errors import PluginErrorInternal
from metagov.core.models import Plugin

logger = logging.getLogger(__name__)


@Registry.plugin
class RevShare(Plugin):
    name = "revshare"

    class Meta:
        proxy = True

    def initialize(self):
        # This state only lasts as long as the plugin does.
        # If the community decides to de-activates the plugin, the plugin instance is deleted and the state is lost.
        self.state.set("pointers", {})

    @Registry.action(
        slug="add-pointer",
        description="Add weighted pointer to revshare config, or update its weight if it already exists",
        input_schema=Schemas.pointer_and_weight,
    )
    def add_pointer(self, parameters):
        pointer = parameters["pointer"]
        weight = parameters["weight"]

        config = self.state.get("pointers")
        config[pointer] = weight
        self.state.set("pointers", config)
        return config

    @Registry.action(
        slug="remove-pointer", description="Remove pointer from revshare config", input_schema=Schemas.pointer
    )
    def remove_pointer(self, parameters):
        pointer = parameters["pointer"]
        config = self.state.get("pointers")
        config.pop(pointer, None)
        self.state.set("pointers", config)
        return config

    @Registry.action(
        slug="replace-config",
        description="Replace revshare config with new config",
        input_schema=Schemas.pointers,
    )
    def replace(self, parameters):
        new_pointers = parameters["pointers"]
        self.state.set("pointers", new_pointers)
        return new_pointers

    @Registry.action(
        slug="get-config",
        description="Get current revshare configuration",
        is_public=True,
    )
    def get_config(self, parameters):
        return self.state.get("pointers")

    @Registry.action(
        slug="pick-pointer",
        description="Choose a random pointer according to weights",
        output_schema=Schemas.pointer,
        is_public=True,
    )
    def pick_pointer(self, parameters):
        pointers = self.state.get("pointers")
        if len(pointers) == 0:
            raise PluginErrorInternal("No pointers")
        # based on https://webmonetization.org/docs/probabilistic-rev-sharing/
        sum_ = sum(list(pointers.values()))
        choice = random.random() * sum_
        for (pointer, weight) in pointers.items():
            choice = choice - weight
            if choice <= 0:
                return {"pointer": pointer}

    @Registry.action(
        slug="discourse-pick-pointer",
        description="Choose a pointer for monetizing a Discourse topic",
        input_schema=Schemas.discourse_pick_pointer_input,
        output_schema=Schemas.pointer,
        is_public=True,
    )
    def discourse_pick_pointer(self, parameters):
        from metagov.plugins.discourse.models import Discourse

        try:
            discourse_plugin = Discourse.objects.get(community=self.community, name="discourse")
        except Discourse.DoesNotExist:
            raise PluginErrorInternal("Discourse plugin is not enabled for this community")

        topic = discourse_plugin.get_topic({"id": parameters["topic_id"]})
        author = topic["details"]["created_by"]["username"]
        participants = [p["username"] for p in topic["details"]["participants"]]
        logger.info(author)
        logger.info(participants)

        # TODO: find payment pointers for author and participants
        # TODO: some logic for choosing payment pointer

        return {"pointer": author}
