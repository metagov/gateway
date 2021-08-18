import requests_mock
from django.test import TestCase
from metagov.plugins.github.models import Github, reactions_to_user_lists
from metagov.tests.plugin_test_utils import PluginTestCase
from test.support import EnvironmentVarGuard # Python >=3


class ApiTests(PluginTestCase):
    def setUp(self):
        self.env = EnvironmentVarGuard()
        self.env.set('GITHUB_APP_ID', 'xx')
        self.env.set('PATH_TO_GITHUB_PRIVATE_KEY', 'xx')
        self.env.set('GITHUB_APP_ID', 'xx')

        # set up mocks needed for the `initialize` method, which is called with the plugin is enabled
        with requests_mock.Mocker() as m:
            m.post(
                f"https://api.github.com/app/installations/1/access_tokens",
                json={"token": "fake"},
            )

            # enable the plugin
            self.enable_plugin(name="github", config={"owner": "dummy", "installation_id": "1"})

    def test_init_works(self):
        """Plugin is properly initialized"""
        plugin = Github.objects.first()
        self.assertIsNotNone(plugin)


class UnitTests(TestCase):
    def test_reactions_to_user_lists(self):
        """Test that the reactions_to_user_lists function counts votes correctly"""
        reactions = [
            {
                "user": {"login": "octocat", "type": "User"},
                "content": "heart",
                "created_at": "2016-05-20T20:09:31Z",
            },
            {
                "user": {"login": "octocat", "type": "User"},
                "content": "+1",
                "created_at": "2016-05-21T20:09:31Z",
            },
            {
                "user": {"login": "foo", "type": "User"},
                "content": "-1",
                "created_at": "2016-05-21T20:09:31Z",
            },
            {
                "user": {"login": "ignored", "type": "Bot"},
                "content": "+1",
                "created_at": "2016-05-21T20:09:31Z",
            },
            {
                "user": {"login": "foo", "type": "User"},
                "content": "+1",
                "created_at": "2016-05-21T20:09:31Z",
            },
        ]

        yes_votes, no_votes = reactions_to_user_lists(reactions)
        self.assertListEqual(yes_votes, ["foo", "octocat"])
        self.assertListEqual(no_votes, ["foo"])

    def test_boolean_reaction_dict_empty(self):
        """Test that the reactions_to_dict function counts votes correctly"""
        reactions = [
            {
                "user": {"login": "foo", "type": "User"},
                "content": "+1",
                "created_at": "2016-05-21T20:09:31Z",
            },
        ]
        yes_votes, no_votes = reactions_to_user_lists(reactions)
        self.assertListEqual(yes_votes, ["foo"])
        self.assertListEqual(no_votes, [])
