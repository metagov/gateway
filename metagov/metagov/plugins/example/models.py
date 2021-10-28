from metagov.core.plugin_manager import Registry, Parameters, VotingStandard
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
        output_schema={"type": "object", "properties": {"lucky_number": {"type": "integer"}}},
    )
    def set_lucky_number(self, lucky_number):
        # [useless example] expose an action for updating plugin state
        self.state.set("lucky_number", lucky_number)
        return {"lucky_number": lucky_number}

    @Registry.action(
        slug="random-int",
        description="Get a random integer in range",
        input_schema={"type": "object", "properties": {"low": {"type": "integer"}, "high": {"type": "integer"}}},
        output_schema={"type": "object", "properties": {"value": {"type": "integer"}}},
    )
    def rand_int(self, low=None, high=None):
        import random

        low = self.config["default_low"] if low is None else low
        high = self.config["default_high"] if high is None else high
        random_number = random.randint(low, high - 1)

        # [useless example] access plugin state
        if random_number == self.state.get("lucky_number"):
            print("You got the lucky number!")

        return {"value": random_number}

    @Registry.event_producer_task()
    def my_task_function(self):
        print("task function called")

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

    def start(self, parameters: Parameters):
        # can safely access parameters, they have already been validated
        print(f'Starting process with options {parameters.options}')

        # can safely access plugin state and config
        print(self.plugin_inst.config["default_high"])
        print(self.plugin_inst.state.get("lucky_number"))

        # save options to internal state
        self.state.set("options", parameters.options)

        # save closing time to internal state
        delay = timedelta(minutes=parameters.delay)
        self.state.set("closing_at", datetime.now(timezone.utc) + delay)

        # mark as PENDING
        self.status = ProcessStatus.PENDING.value
        self.save()

    def update(self):
        closing_at = self.state.get("closing_at")
        if datetime.now(timezone.utc) >= closing_at:
            self.close()

    def close(self):
        print("Closing process")

        options = self.state.get("options")

        # use `plugin_inst` to access plugin functions
        result = self.plugin_inst.rand_int(low=0, high=len(options))
        rand_index = result["value"]
        print(f"Winner is {options[rand_index]}!")

        self.outcome = {"winner": options[rand_index]}
        self.status = ProcessStatus.COMPLETED.value
        self.save()
