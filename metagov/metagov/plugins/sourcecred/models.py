import json
import requests
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotFound
from metagov.core.plugin_models import register_resource, load_settings


settings = load_settings("sourcecred")

input_schema = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "username": {
            "description": "Username on the platform used with this sourcecred instance",
            "type": "string"
        }
    },
    "required": [
        "username"
    ]
}

output_schema = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "value": {
            "description": "Users most recent Cred value",
            "type": "number"
        }
    }
}


@register_resource(
    slug='sourcecred.cred',
    description='Cred value for given user',
    input_schema=input_schema,
    output_schema=output_schema
)
def cred(parameters):
    username = parameters["username"]
    cred = get_user_cred(username)
    if cred is None:
        # can we specify Not Found?
        raise Exception(f"{username} not found in sourcecred instance")
    return {"value": cred}


def get_user_cred(username):
    url = f"{settings['sourcecred_server']}/output/accounts.json"
    resp = requests.get(url)
    cred_data = resp.json()
    for account in cred_data["accounts"]:
        name = account["account"]["identity"]["name"]
        if name == username:
            return account["totalCred"]
    return None
