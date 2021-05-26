from django.test import Client, TestCase


class PluginTestCase(TestCase):
    COMMUNITY_NAME = "test-community"
    COMMUNITY_URL = "/api/internal/community/test-community"
    COMMUNITY_HEADER = {"HTTP_X_METAGOV_COMMUNITY": "test-community"}

    def _pre_setup(self):
        # Create community with no plugins enabled
        self.client = Client()
        self.client.put(self.COMMUNITY_URL, data={"name": self.COMMUNITY_NAME}, content_type="application/json")
        super(PluginTestCase, self)._pre_setup()

    def _post_teardown(self):
        super(PluginTestCase, self)._post_teardown()

    def enable_plugin(self, name, config=None):
        response = self.client.get(self.COMMUNITY_URL)
        data = response.json()
        plugins = [x for x in data["plugins"] if not x["name"] == name]
        plugins.append({"name": name, "config": config})
        data["plugins"] = plugins
        self.client.put(self.COMMUNITY_URL, data=data, content_type="application/json")
        return data

    def disable_plugin(self, name):
        response = self.client.get(self.COMMUNITY_URL)
        data = response.json()
        plugins = [x for x in data["plugins"] if not x["name"] == name]
        data["plugins"] = plugins
        self.client.put(self.COMMUNITY_URL, data=data, content_type="application/json")
        return data