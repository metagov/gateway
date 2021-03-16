import json
import random
import ast

from metagov.core.plugin_models import register_resource, load_settings


settings = load_settings("webmonetization")

pointers_str = settings['revshare_config']
pointers = ast.literal_eval(pointers_str)

output_schema = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "pointer": {
            "description": "Randomly chosen payment pointer",
            "type": "string"
        }
    }
}

@register_resource(
    slug='webmonetization.revshare',
    description='Rev share configuration',
    input_schema=None,
    output_schema=output_schema
)
def pick_pointer(parameters):
    # based on https://webmonetization.org/docs/probabilistic-rev-sharing/
    sum_ = sum(list(pointers.values()))
    choice = random.random() * sum_
    for (pointer, weight) in pointers.items():
        choice = choice - weight
        if choice <= 0:
            return {"pointer": pointer}
