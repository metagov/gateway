import metagov.plugins.discourse.tests.mocks as DiscourseMock
import requests
import requests_mock
from metagov.core.tasks import execute_plugin_tasks
from metagov.plugins.discourse.models import Discourse, DiscoursePoll
from metagov.tests.plugin_test_utils import PluginTestCase

mock_server_url = "https://discourse.metagov.org"
discourse_process_url = "/api/internal/process/discourse.poll"

session = requests.Session()
adapter = requests_mock.Adapter()
session.mount("mock://", adapter)

adapter.register_uri("GET", "mock://test.com", text="data")


class ApiTests(PluginTestCase):
    def setUp(self):
        # set up mocks needed for the `initialize` method, which is called with the plugin is enabled
        with requests_mock.Mocker() as m:
            m.get(f"{mock_server_url}/about.json", json={"about": {"title": "my community"}})
            m.get(
                f"{mock_server_url}/admin/users/list/active.json",
                json=[{"id": 1, "username": "alice"}],
            )
            m.get(
                f"{mock_server_url}/admin/users/1.json",
                json={"id": 1, "username": "alice", "foo": "bar"},
            )

            # enable the plugin
            self.enable_plugin(
                name="discourse", config={"server_url": mock_server_url, "api_key": "empty", "webhook_secret": "empty"}
            )

    def test_init_works(self):
        """Plugin is properly initialized"""
        plugin = Discourse.objects.first()
        self.assertIsNotNone(plugin)
        self.assertEqual(plugin.state.get("users").get("1").get("username"), "alice")

    def start_discourse_poll(self):
        self.assertEqual(DiscoursePoll.objects.all().count(), 0)

        with requests_mock.Mocker() as m:
            # mock Discourse response to creating a new poll
            mock_response = {"id": 1, "topic_id": 0, "topic_slug": "test", "post_number": 1}
            m.post(f"{mock_server_url}/posts.json", json=mock_response)
            # mock Discourse response to getting a post
            m.get(f"{mock_server_url}/posts/1.json", json=DiscourseMock.post_with_open_poll)

            # make Metagov API request to create a new poll
            input_params = {
                "title": "a test poll",
                "options": ["a", "b", "c"],
                "category": 8,
                "closing_at": "2023-04-22",
            }
            response = self.client.post(
                discourse_process_url, data=input_params, content_type="application/json", **self.COMMUNITY_HEADER
            )
            self.assertEqual(response.status_code, 202)
            location = response["location"]

            # status should be pending
            response = self.client.get(location, content_type="application/json")
            self.assertContains(response, "poll_url")

            process = DiscoursePoll.objects.first()
            self.assertEqual(process.status, "pending")

            # change mock to include some votes
            m.get(f"{mock_server_url}/posts/1.json", json=DiscourseMock.post_with_open_poll_and_votes)

            # call celery task function, which should invoke process.update()
            execute_plugin_tasks()

            # status should still be pending
            response = self.client.get(location, content_type="application/json")
            self.assertContains(response, "poll_url")
            self.assertContains(response, "pending")
            self.assertContains(response, "25")  # current vote count is included in the response

            return (location, process)

    def test_discourse_poll_closed_in_discourse(self):
        """SCENARIO: user closed the vote early in discourse"""
        self.assertEqual(DiscoursePoll.objects.all().count(), 0)

        location, process = self.start_discourse_poll()

        with requests_mock.Mocker() as m:
            # change mock to be closed
            m.get(f"{mock_server_url}/posts/1.json", json=DiscourseMock.post_with_closed_poll_and_votes)

            # call celery task function, which should invoke process.update()
            execute_plugin_tasks()

            # status should be completed
            response = self.client.get(location, content_type="application/json")
            self.assertContains(response, "poll_url")
            self.assertContains(response, "completed")
            self.assertContains(response, "35")  # current vote count is included in the response

    def test_discourse_poll_close(self):
        """SCENARIO: driver closes vote early using DELETE request"""
        self.assertEqual(DiscoursePoll.objects.all().count(), 0)

        location, process = self.start_discourse_poll()

        with requests_mock.Mocker() as m:
            # mock toggle_status
            m.put(f"{mock_server_url}/polls/toggle_status", json=DiscourseMock.toggle_response_closed)

            # status should be completed
            response = self.client.delete(location, content_type="application/json")
            self.assertContains(response, "poll_url")
            self.assertContains(response, "completed")
            self.assertContains(response, "35")  # vote count from the toggle response is the final outcome
