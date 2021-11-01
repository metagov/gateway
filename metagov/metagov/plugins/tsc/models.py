from metagov.core.plugin_manager import AuthorizationType, Registry, Parameters, VotingStandard
from metagov.core.models import Plugin

import requests

@Registry.plugin
class TSC(Plugin):
    name = "tsc"
    config_schema = {
        "type": "object",
        "properties": {
            "server_url": {"type": "string"}
        },
        "required": ["server_url"]
    }

    class Meta:
        proxy = True

    @Registry.action(
        slug="get-user",
        description="Returns information about the requested user",
        input_schema={
            "type": "object",
            "properties": {
                "user_id": {"type": "string"}
            },
            "required": ["user_id"]
        }
    )
    def get_user(self, user_id):
        url = self.config['server_url'] + '/api/user/' + user_id
        response = requests.get(url)

        return response.json()


    @Registry.action(
        slug='get-contract',
        description='Returns information about the requested contract',
        input_schema={
            'type': 'object',
            'properties': {
                'contract_id': {'type': 'string'}
            },
            'required': ['contract_id']
        }
    )
    def get_contract(self, contract_id):
        url = self.config['server_url'] + '/api/contract/' + contract_id
        response = requests.get(url)

        return response.json()
    
    @Registry.action(
        slug='get-execution',
        description='Returns information about the requested execution',
        input_schema={
            'type': 'object',
            'properties': {
                'execution_id': {'type': 'string'}
            },
            'required': ['execution_id']
        }
    )
    def get_execution(self, execution_id):
        url = self.config['server_url'] + '/api/execution/' + execution_id
        response = requests.get(url)

        return response.json()
    
    @Registry.action(
        slug='get-agreement',
        description='Returns information about the requested agreement',
        input_schema={
            'type': 'object',
            'properties': {
                'agreement_id': {'type': 'string'}
            },
            'required': ['agreement_id']
        }
    )
    def get_agreement(self, agreement_id):
        url = self.config['server_url'] + '/api/agreement/' + agreement_id
        response = requests.get(url)

        return response.json()
