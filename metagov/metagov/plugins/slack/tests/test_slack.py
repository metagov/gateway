import requests_mock
from django.test import TestCase
from metagov.plugins.slack.models import Slack
from metagov.tests.plugin_test_utils import PluginTestCase


class ApiTests(PluginTestCase):
    def setUp(self):
        self.enable_plugin(
            name="slack", config={"team_id": "123", "team_name": "test", "bot_token": "empty", "bot_user-id": "001"}
        )

    def test_init_works(self):
        """Plugin is properly initialized"""
        plugin = Slack.objects.first()
        self.assertIsNotNone(plugin)
