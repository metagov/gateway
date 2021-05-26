from metagov.plugins.revshare.models import RevShare
from metagov.tests.plugin_test_utils import PluginTestCase


class ApiTests(PluginTestCase):
    def setUp(self):
        self.enable_plugin(name="revshare")

    def test_revshare(self):
        """Test adding, removing, and requesting pointer from default key"""
        self.assertEqual(RevShare.objects.all().count(), 1)

        # add a pointer
        parameters = {"pointer": "$alice.example", "weight": 1}
        response = self.client.post(
            "/api/internal/action/revshare.add-pointer",
            data={"parameters": parameters},
            content_type="application/json",
            **self.COMMUNITY_HEADER,
        )
        self.assertContains(response, "$alice.example")

        # request a random pointer
        response = self.client.post(
            "/api/action/revshare.pick-pointer", content_type="application/json", **self.COMMUNITY_HEADER
        )
        self.assertContains(response, "$alice.example")

        # get config
        response = self.client.post(
            "/api/action/revshare.get-config", content_type="application/json", **self.COMMUNITY_HEADER
        )
        self.assertContains(response, "$alice.example")

        # remove a pointer
        parameters = {"pointer": "$alice.example"}
        response = self.client.post(
            "/api/internal/action/revshare.remove-pointer",
            data={"parameters": parameters},
            content_type="application/json",
            **self.COMMUNITY_HEADER,
        )
        self.assertNotContains(response, "$alice.example")

    def test_revshare(self):
        """Test adding, removing, and requesting pointer using different keys"""
        self.assertEqual(RevShare.objects.all().count(), 1)

        key1 = "GROUP_1"
        key2 = "GROUP_2"

        # add a pointer to group 1
        parameters = {"pointer": "$alice.example", "weight": 1, "key": key1}
        response = self.client.post(
            "/api/internal/action/revshare.add-pointer",
            data={"parameters": parameters},
            content_type="application/json",
            **self.COMMUNITY_HEADER,
        )
        self.assertContains(response, "$alice.example")

        # add a pointer to group 2
        parameters = {"pointer": "$bob.example", "weight": 1, "key": key2}
        response = self.client.post(
            "/api/internal/action/revshare.add-pointer",
            data={"parameters": parameters},
            content_type="application/json",
            **self.COMMUNITY_HEADER,
        )
        self.assertContains(response, "$bob.example")
        self.assertNotContains(response, "$alice.example")

        # request a pointer from group 2
        response = self.client.post(
            "/api/action/revshare.pick-pointer",
            data={"parameters": {"key": key2}},
            content_type="application/json",
            **self.COMMUNITY_HEADER,
        )
        self.assertContains(response, "$bob.example")

        # remove a pointer from group 2
        parameters = {"pointer": "$bob.example", "key": key2}
        response = self.client.post(
            "/api/internal/action/revshare.remove-pointer",
            data={"parameters": parameters},
            content_type="application/json",
            **self.COMMUNITY_HEADER,
        )
        self.assertNotContains(response, "$bob.example")

        # get config for group 2 (should be empty now)
        parameters = {"key": key2}
        response = self.client.post(
            "/api/internal/action/revshare.get-config",
            data={"parameters": parameters},
            content_type="application/json",
            **self.COMMUNITY_HEADER,
        )
        self.assertContains(response, "{}")
