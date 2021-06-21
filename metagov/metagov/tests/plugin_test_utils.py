from django.test import Client, TestCase


class PluginTestCase(TestCase):
    def _pre_setup(self):
        # Create community with no plugins enabled
        self.client = Client()
        response = self.client.post(
            "/api/internal/community", data={"readable_name": "my community"}, content_type="application/json"
        )
        data = response.json()

        self.COMMUNITY_SLUG = data["slug"]
        self.COMMUNITY_URL = f"/api/internal/community/{data['slug']}"
        self.COMMUNITY_HEADER = {"HTTP_X_METAGOV_COMMUNITY": self.COMMUNITY_SLUG}

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