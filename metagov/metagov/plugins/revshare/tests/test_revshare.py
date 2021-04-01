from django.test import Client, TestCase
from metagov.core.models import Community, Plugin
from metagov.plugins.revshare.models import RevShare


class ApiTests(TestCase):
    def setUp(self):
        # create a test community with the revshare plugin enabled
        self.client = Client()

        self.community_name = "revshare-test-community"
        self.headers = {"HTTP_X_METAGOV_COMMUNITY": self.community_name}
        self.community_url = f"/api/internal/community/{self.community_name}"
        self.community_data = {
            "name": self.community_name,
            "readable_name": "miriams new community",
            "plugins": [{"name": "revshare", "config": {}}],
        }
        # create a community with the revshare plugin enabled
        self.client.put(self.community_url, data=self.community_data, content_type="application/json")

    def test_revshare(self):
        self.assertEqual(RevShare.objects.all().count(), 1)

        # add a pointer
        parameters = {"pointer": "$alice.example", "weight": 1}
        response = self.client.post(
            "/api/internal/action/revshare.add-pointer",
            data={"parameters": parameters},
            content_type="application/json",
            **self.headers,
        )
        self.assertContains(response, "$alice.example")

        # request a random pointer
        response = self.client.get(
            "/api/action/revshare.pick-pointer", content_type="application/json", **self.headers
        )
        self.assertContains(response, "$alice.example")
