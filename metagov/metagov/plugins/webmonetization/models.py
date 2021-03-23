import ast
import json
import random

import metagov.core.plugin_decorators as Registry
from metagov.core.models import Plugin


@Registry.plugin
class WebMonetization(Plugin):
    name = "webmonetization"
    config_schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "revshare_config": {
                "description": "json blob as a string",
                "type": "string",
                "default": "{\"$alice.example\": 50,\"$bob.example\": 40,\"$connie.example\": 9.5,\"$dave.example\": 0.5}"
            }
        },
        "required": [
            "revshare_config"
        ]
    }

    class Meta:
        proxy = True

    @Registry.resource(
        slug='revshare',
        description='Cred value for given user',
        input_schema=None,
        output_schema={
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "pointer": {
                    "description": "Randomly chosen payment pointer",
                    "type": "string"
                }
            }
        }
    )
    def pick_pointer(self, parameters):
        pointers = ast.literal_eval(self.config['revshare_config'])
        # based on https://webmonetization.org/docs/probabilistic-rev-sharing/
        sum_ = sum(list(pointers.values()))
        choice = random.random() * sum_
        for (pointer, weight) in pointers.items():
            choice = choice - weight
            if choice <= 0:
                return {"pointer": pointer}
