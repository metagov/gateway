import json
import requests
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotFound
from metagov.core.plugins import ResourceProvider
from metagov.core.plugins.sourcecred import conf

class SourceCred(ResourceProvider):
    slug = 'cred'

    def __init__(self):
        self.server_url = conf.SOURCECRED_SERVER

    def retrieve_resource(self, querydict):
        username = querydict.get("username", None)
        if not username:
            return HttpResponseBadRequest("'username' query attribute missing")
        cred = self.__get_user_cred(username)
        if cred is None:
            return HttpResponseNotFound(f"{username} not found in sourcecred instance")
        return HttpResponse(json.dumps({ "value": cred }))
    
    def __get_user_cred(self, username):
        url = f"{self.server_url}/output/accounts.json"
        resp = requests.get(url)
        cred_data = resp.json()
        for account in cred_data["accounts"]:
            name = account["account"]["identity"]["name"]
            if name == username:
                return account["totalCred"]
        return None
