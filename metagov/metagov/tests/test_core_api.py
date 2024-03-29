from django.test import Client, TestCase
from metagov.core.models import Community, GovernanceProcess, Plugin
from metagov.core.signals import governance_process_updated
from metagov.plugins.example.models import Randomness, StochasticVote
from metagov.plugins.sourcecred.models import SourceCred
from .plugin_test_utils import catch_signal


class UnitTests(TestCase):
    def test_voting_input_params(self):
        """Test Voting input parameter schema construction, and Parameters"""
        from metagov.core.plugin_manager import Parameters, VotingStandard

        extra_properties = {
            "foobar": {"type": "string", "enum": ["foo", "bar"], "default": "bar"},
            "numeric": {"type": "number"},
        }

        schema = VotingStandard.create_input_schema(
            include=["title", "closing_at"],
            extra_properties=extra_properties,
            required=["field_without_default", "title"],
        )
        values = {"title": "my vote", "numeric": 8}
        params = Parameters(values=values, schema=schema)
        self.assertEqual(params.foobar, "bar")
        self.assertEqual(params.title, "my vote")
        self.assertEqual(params.numeric, 8)
        self.assertEqual(params.closing_at, None)
        self.assertIsNotNone(params._json)

        # Create Parameters with no schema
        params = Parameters(values=values)
        self.assertEqual(params.title, "my vote")
        self.assertEqual(params.numeric, 8)
        self.assertDictEqual(params._json, values)


class ApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.community_url = "/api/internal/community"

    def test_community(self):
        client = Client()
        data = {"readable_name": "new community for api test"}

        # bad request (update community that doesn't exist)
        response = client.put(f"{self.community_url}/nonexistent", data=data, content_type="application/json")
        self.assertEqual(response.status_code, 404)

        # good request to create community

        response = client.post(self.community_url, data=data, content_type="application/json")
        self.assertEqual(response.status_code, 201)
        data = response.json()
        community_slug = data["slug"]
        url = f"{self.community_url}/{community_slug}"

        self.assertEqual(Community.objects.all().count(), 1)
        # there should be no plugins
        self.assertEqual(Plugin.objects.all().count(), 0)

        community = Community.objects.all().first()

        # bad request to activate plugin
        data["plugins"] = [{"name": "nonexistent-plugin"}]
        response = client.put(url, data=data, content_type="application/json")
        # name and slug dont match
        self.assertContains(response, "No such plugin registered", status_code=400)

        # bad request to activate plugin
        data["plugins"] = [{"name": "sourcecred", "config": {"wrongkey": "test"}}]
        response = client.put(url, data=data, content_type="application/json")
        self.assertContains(response, "Validation", status_code=400)

        # bad sourcecred request (missing header)
        sourcecred_request_url = "/api/internal/action/sourcecred.user-cred"
        response = client.post(
            sourcecred_request_url,
            data={"parameters": {"username": "miriam"}},
            content_type="application/json",
        )
        self.assertContains(response, "Missing required header 'X-Metagov-Community'", status_code=400)

        # bad sourcecred request (plugin not activated)
        headers = {"HTTP_X_METAGOV_COMMUNITY": community_slug}
        sourcecred_request_url = "/api/internal/action/sourcecred.user-cred"
        response = client.post(
            sourcecred_request_url,
            data={"parameters": {"username": "miriam"}},
            content_type="application/json",
            **headers,
        )
        self.assertContains(response, "not enabled for community", status_code=400)

        # good request to activate plugin
        sc_server = "https://metagov.github.io/sourcecred-instance"
        data["plugins"] = [{"name": "sourcecred", "config": {"server_url": sc_server}}]
        response = client.put(url, data=data, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        plugins = Plugin.objects.filter(community=community, name="sourcecred")
        self.assertEqual(plugins.count(), 1)
        self.assertEqual(plugins.first().community_platform_id, sc_server)
        sc_proxy_plugins = SourceCred.objects.filter(community=community, name="sourcecred")
        self.assertEqual(sc_proxy_plugins.count(), 1)
        self.assertEqual(sc_proxy_plugins.first().community_platform_id, sc_server)

        # good sourcecred request (plugin is activated)
        sourcecred_request_url = "/api/internal/action/sourcecred.user-cred"
        response = client.post(
            sourcecred_request_url,
            data={"parameters": {"username": "miriam"}},
            content_type="application/json",
            **headers,
        )
        self.assertContains(response, '"value":')

        # Doesn't work if neither a username nor an id is sent
        sourcecred_request_url = "/api/internal/action/sourcecred.user-cred"
        response = client.post(
            sourcecred_request_url,
            data={"parameters": {}},
            content_type="application/json",
            **headers,
        )
        self.assertContains(response, "Either a username or an id argument is required", status_code=500)

        # works on an existing id
        sourcecred_request_url = "/api/internal/action/sourcecred.user-cred"
        response = client.post(
            sourcecred_request_url,
            data={"parameters": {"id": "hozzjss"}},
            content_type="application/json",
            **headers,
        )
        self.assertContains(response, '"value":')

        # activate randomness plugin
        data["plugins"].append({"name": "randomness", "config": {"default_low": 2, "default_high": 200}})
        response = client.put(url, data=data, content_type="application/json")
        self.assertEqual(response.status_code, 200)

        # there are two active plugins: sourcecred and example-plugin
        self.assertEqual(Plugin.objects.filter(community=community).count(), 2)
        # only returns matching proxy models
        self.assertEqual(Randomness.objects.filter(community=community).count(), 1)

        self.assertEqual(Plugin.objects.get(name="randomness").config["default_high"], 200)

        # perform stochastic-vote process

        # start process
        vote_input = {"options": ["one", "two", "three"], "delay": 2}
        response = client.post(
            "/api/internal/process/randomness.delayed-stochastic-vote",
            data=vote_input,
            content_type="application/json",
            **headers,
        )
        self.assertEqual(response.status_code, 202)
        self.assertTrue(response.has_header("location"))
        location = response.get("location")

        # assert created
        self.assertEqual(GovernanceProcess.objects.all().count(), 1)
        self.assertEqual(StochasticVote.objects.all().count(), 1)
        process = StochasticVote.objects.all().first()

        # poll process
        response = client.get(location, content_type="application/json")
        self.assertContains(response, "pending")

        # close process early, assert that signal is emitted
        with catch_signal(governance_process_updated) as handler:
            response = client.delete(location, content_type="application/json")

            # assert that the signal is correct
            handler.assert_called_once()
            kwargs = handler.call_args.kwargs
            self.assertEqual(kwargs["status"], "completed")
            self.assertIsNotNone(kwargs["outcome"]["winner"])

            # assert that the http response is correct
            self.assertContains(response, "completed")
            self.assertContains(response, "winner")

        # deactivate one plugin
        data["plugins"].pop()
        response = client.put(url, data=data, content_type="application/json")
        self.assertEqual(Plugin.objects.filter(community=community).count(), 1)

        # deactivate another plugin
        data["plugins"].pop()
        response = client.put(url, data=data, content_type="application/json")
        self.assertEqual(Plugin.objects.filter(community=community).count(), 0)
