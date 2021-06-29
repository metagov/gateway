import requests_mock
from django.test import TestCase
from metagov.plugins.slack.models import Slack, SlackEmojiVote, reactions_to_dict
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


class UnitTests(TestCase):
    def test_boolean_reaction_dict(self):
        """Test that the reactions_to_dict function collapses thumb votes correctly"""
        reactions = [
            {"name": "-1", "users": ["B1", "U1", "U2"], "count": 2},
            {"name": "-1::skin-tone-2", "users": ["B1", "U2"], "count": 1},
            {"name": "-1::skin-tone-6", "users": ["B1", "U3"], "count": 1},
            {"name": "+1", "users": ["B1", "U4"], "count": 1},
            {"name": "blue_heart", "users": ["U4"], "count": 1},
            {"name": "yellow_heart", "users": ["U4"], "count": 1},
        ]
        emoji_to_option = {"+1": "yes", "-1": "no"}
        votes = reactions_to_dict(
            reactions,
            emoji_to_option,
            excluded_users=["B1"],
        )
        self.assertDictEqual(
            votes,
            {
                "no": {"users": ["U1", "U2", "U3"], "count": 3},
                "yes": {"users": ["U4"], "count": 1},
            },
        )

    def test_choice_reaction_dict(self):
        """Test that the reactions_to_dict function collapses votes correctly"""
        reactions = [
            {"name": "blue_heart", "users": ["U1", "U2"], "count": 2},
            {"name": "yellow_heart", "users": ["U1", "U3"], "count": 2},
        ]
        emoji_to_option = {"blue_heart": "opt_1", "yellow_heart": "opt_2", "purple_heart": "opt_3"}
        votes = reactions_to_dict(reactions, emoji_to_option)
        self.assertDictEqual(
            votes,
            {
                "opt_1": {"users": ["U1", "U2"], "count": 2},
                "opt_2": {"users": ["U1", "U3"], "count": 2},
                "opt_3": {"users": [], "count": 0},
            },
        )