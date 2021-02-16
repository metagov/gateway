import json
import requests
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotFound
from metagov.core.plugin_models import retrieve_resource, load_settings


settings = load_settings("sourcecred")


@retrieve_resource('cred', 'Cred value for given user')
def cred(querydict):
    username = querydict.get("username")
    if not username:
        return HttpResponseBadRequest("'username' query attribute missing")
    cred = get_user_cred(username)
    if cred is None:
        return HttpResponseNotFound(f"{username} not found in sourcecred instance")
    return HttpResponse(json.dumps({"value": cred}))


@retrieve_resource('grain', 'Grain value for given user')
def grain(querydict):
    username = querydict.get("username")
    if not username:
        return HttpResponseBadRequest("'username' query attribute missing")
    cred = get_user_cred(username)
    if cred is None:
        return HttpResponseNotFound(f"{username} not found in sourcecred instance")
    return HttpResponse(json.dumps({"value": cred}))


def get_user_cred(username):
    url = f"{settings['sourcecred_server']}/output/accounts.json"
    resp = requests.get(url)
    cred_data = resp.json()
    for account in cred_data["accounts"]:
        name = account["account"]["identity"]["name"]
        if name == username:
            return account["totalCred"]
    return None
