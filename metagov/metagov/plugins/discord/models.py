import asyncio
import discord
import environ
import json
import logging
import requests

from metagov.core.models import GovernanceProcess, Plugin, ProcessStatus, AuthType
from metagov.core.plugin_manager import Registry
from rest_framework.exceptions import ValidationError
from threading import Thread

logger = logging.getLogger(__name__)

env = environ.Env()
environ.Env.read_env()

client = discord.Client()


@Registry.plugin
class Discord(Plugin):
    name = "discord"
    auth_type = AuthType.OAUTH
    config_schema = {
        "type": "object",
        "properties": {
            # these are set automatically if using the oauth flow
            "guild_id": {"description": "Discord Guild ID", "type": "number"},
            "guild_name": {"description": "Discord Guild Name", "type": "string"},
        },
    }

    class Meta:
        proxy = True

loop = asyncio.get_event_loop()
loop.create_task(client.start(env("DISCORD_BOT_TOKEN")))
Thread(target=loop.run_forever).start()
