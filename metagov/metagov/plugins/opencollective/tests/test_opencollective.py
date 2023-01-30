import requests_mock
from metagov.plugins.opencollective.models import OpenCollective
from metagov.tests.plugin_test_utils import PluginTestCase


class ApiTests(PluginTestCase):
    def setUp(self):
        # set up mocks needed for the `initialize` method, which is called with the plugin is enabled
        with requests_mock.Mocker() as m:
            m.post(
                "https://api.opencollective.com/graphql/v2",
                json={"data": {"collective": {"name": "my community", "id": "xyz", "legacyId": 123}}},
            )
            # enable the plugin
            self.enable_plugin(name="opencollective", config={"collective_slug": "mycollective", "access_token": "empty"})

    def test_init_works(self):
        """Plugin is properly initialized"""
        plugin = OpenCollective.objects.first()
        self.assertIsNotNone(plugin)
        self.assertEqual(plugin.state.get("collective_name"), "my community")
