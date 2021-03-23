import metagov.core.plugin_decorators as Registry
from metagov.core.models import GovernanceProcess, Plugin, ProcessStatus


@Registry.plugin
class ExamplePlugin(Plugin):
    name = 'example-plugin'
    config_schema = {
        "type": "object",
        "properties": {
            "lucky_number": {"type": "integer"}
        },
        "required": ["lucky_number"]
    }

    class Meta:
        proxy = True

    def initialize(self):
        print(
            f'Initialized plugin with lucky number: {self.config["lucky_number"]}.')
        print(f'This instance belongs to community {self.community}.')
        # Persist something in state
        self.state.set('lucky_color', 'red')

    @Registry.action(
        slug='action',
        description='Perform an action on behalf of a user'
    )
    def do_something(self, parameters, initiator):
        print('Performing an action')
        return {'id': 123}

    @Registry.resource(
        slug='random-int',
        description='Get a random integer'
    )
    def rand_int(self, parameters):
        import random
        low = parameters.get('low', 0)
        high = parameters.get('high', 9)
        return {'value': random.randint(low, high)}


@Registry.governance_process
class StochasticVote(GovernanceProcess):
    name = 'stochastic-vote'
    plugin_name = 'example-plugin'
    input_schema = {
        "type": "object",
        "properties": {
            "options": {
                "type": "array",
                "items": {"type": "string"}
            },
        },
        "required": ["options"]
    }

    class Meta:
        proxy = True

    def start(self, parameters):
        # can safely access parameters, they have already been validated
        print(f'Starting process with options {parameters["options"]}')

        # can safely access plugin config
        print(self.plugin.config['lucky_number'])

        # save options into internal state
        self.state.set('options', parameters['options'])

        # set some data and mark "pending", even though stochastic vote isn't really asynchronous
        self.data = {'this is': 'data'}
        self.status = ProcessStatus.PENDING.value
        self.save()

    def close(self):
        print('Closing process')

        options = self.state.get('options')

        # use plugin function
        result = self.plugin.rand_int({'low': 0, 'high': len(options)})
        rand_index = result['value']
        print(f"Winner is {options[rand_index]}!")

        self.outcome = {'winner': options[rand_index]}
        self.status = ProcessStatus.COMPLETED.value
        self.save()
