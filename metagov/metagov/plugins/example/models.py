import metagov.core.plugin_decorators as Registry
from metagov.core.models import GovernanceProcess, Plugin, ProcessStatus
from datetime import datetime, timezone, timedelta


@Registry.plugin
class Randomness(Plugin):
    """
    Example plugin implementing randomness
    """

    name = "randomness"
    config_schema = {
        "type": "object",
        "properties": {"default_low": {"type": "integer"}, "default_high": {"type": "integer"}},
        "required": ["default_low", "default_high"],
    }

    class Meta:
        proxy = True

    def initialize(self):
        print(f"Initialized plugin with config: {self.config}")
        print(f"This instance belongs to community: {self.community}")
        # [useless example] persist something in plugin state
        self.state.set("lucky_number", 4)

    @Registry.action(
        slug="set-lucky-number",
        description="Set lucky number",
        input_schema={
            "type": "object",
            "properties": {"lucky_number": {"type": "integer"}},
            "required": ["lucky_number"],
        },
    )
    def set_lucky_number(self, parameters, initiator):
        # [useless example] expose an action for updating plugin state
        self.state.set("lucky_number", parameters["lucky_number"])
        return {"lucky_number": parameters["lucky_number"]}

    @Registry.resource(
        slug="random-int",
        description="Get a random integer in range",
        input_schema={
            "type": "object",
            "properties": {"low": {"type": "integer"}, "high": {"type": "integer"}}
        }
    )
    def rand_int(self, parameters):
        import random

        low = parameters.get("low", self.config["default_low"])
        high = parameters.get("high", self.config["default_high"])
        random_number = random.randint(low, high - 1)

        # [useless example] access plugin state
        if random_number == self.state.get("lucky_number"):
            print("You got the lucky number!")

        return {"value": random_number}


@Registry.governance_process
class StochasticVote(GovernanceProcess):
    name = "delayed-stochastic-vote"
    plugin_name = "randomness"
    input_schema = {
        "type": "object",
        "properties": {
            "options": {"type": "array", "items": {"type": "string"}},
            "delay": {"type": "integer", "description": "number of minutes to delay the stochastic vote"},
        },
        "required": ["options", "delay"],
    }

    class Meta:
        proxy = True

    def start(self, parameters):
        # can safely access parameters, they have already been validated
        print(f'Starting process with options {parameters["options"]}')

        # can safely access plugin state and config
        print(self.plugin.config['default_high'])
        print(self.plugin.state.get("lucky_number"))

        # save options to internal state
        self.state.set("options", parameters["options"])

        # save closing time to internal state
        delay = timedelta(minutes=parameters["delay"])
        self.state.set("closing_at", datetime.now(timezone.utc) + delay)

        # mark as PENDING
        self.status = ProcessStatus.PENDING.value
        self.save()

    def poll(self):
        closing_at = self.state.get("closing_at")
        if datetime.now(timezone.utc) >= closing_at:
            self.close()

    def close(self):
        print("Closing process")

        options = self.state.get("options")

        # use `get_plugin()` to get access to plugin functions
        result = self.get_plugin().rand_int({"low": 0, "high": len(options)})
        rand_index = result["value"]
        print(f"Winner is {options[rand_index]}!")

        self.outcome = {"winner": options[rand_index]}
        self.status = ProcessStatus.COMPLETED.value
        self.save()
