import ast
import json
import logging
import random

import metagov.core.plugin_decorators as Registry
import metagov.plugins.webmonetization.schemas as Schemas
from metagov.core.models import Plugin

logger = logging.getLogger('django')


@Registry.plugin
class WebMonetization(Plugin):
    name = "webmonetization"

    class Meta:
        proxy = True

    def initialize(self):
        # This state only lasts as long as the plugin does.
        # If the community deletes and re-enables this plugin, the state is lost.
        self.state.set('pointers', {})

    @Registry.action(
        slug="update-pointer",
        description="Add weighted pointer to revshare config, or update its weight if it already exists",
        input_schema=Schemas.pointer_and_weight
    )
    def update_pointer(self, parameters, initiator):
        pointer = parameters['pointer']
        weight = parameters['weight']

        config = self.state.get('pointers')
        config[pointer] = weight
        self.state.set('pointers', config)
        return config

    @Registry.action(
        slug="remove-pointer",
        description="Remove pointer from revshare config",
        input_schema=Schemas.pointer
    )
    def remove_pointer(self, parameters, initiator):
        pointer = parameters['pointer']
        config = self.state.get('pointers')
        config.pop(pointer, None)
        self.state.set('pointers', config)
        return config

    @Registry.action(
        slug="replace-pointers",
        description="Replace entire revshare config with new pointers",
        input_schema=Schemas.pointers
    )
    def replace(self, parameters, initiator):
        new_pointers = parameters['pointers']
        self.state.set('pointers', new_pointers)
        return new_pointers

    @Registry.resource(
        slug='revshare-config',
        description='Current revshare configuration'
    )
    def get_config(self, parameters):
        return self.state.get('pointers')

    @Registry.resource(
        slug='revshare-pointer',
        description='Randomly selected pointer',
        input_schema=None,
        output_schema=Schemas.pointer
    )
    def pick_pointer(self, parameters):
        pointers = self.state.get('pointers')
        if len(pointers) == 0:
            raise Exception("No pointers")
        # based on https://webmonetization.org/docs/probabilistic-rev-sharing/
        sum_ = sum(list(pointers.values()))
        choice = random.random() * sum_
        for (pointer, weight) in pointers.items():
            choice = choice - weight
            if choice <= 0:
                return {"pointer": pointer}
