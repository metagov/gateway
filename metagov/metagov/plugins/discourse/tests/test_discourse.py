from django.test import Client, TestCase
from metagov.plugins.discourse.models import Discourse, DiscoursePoll
import metagov.plugins.discourse.tests.mocks as DiscourseMock
import requests_mock
import requests

mock_server_url = "https://discourse.metagov.org"
discourse_process_url = "/api/internal/process/discourse.poll"

session = requests.Session()
adapter = requests_mock.Adapter()
session.mount("mock://", adapter)

adapter.register_uri("GET", "mock://test.com", text="data")


class ApiTests(TestCase):
    def setUp(self):
        # create a test community with the revshare plugin enabled
        self.client = Client()

        self.community_name = "test-community"
        self.headers = {"HTTP_X_METAGOV_COMMUNITY": self.community_name}
        self.community_url = f"/api/internal/community/{self.community_name}"
        self.community_data = {
            "name": self.community_name,
            "plugins": [
                {
                    "name": "discourse",
                    "config": {"server_url": mock_server_url, "api_key": "empty", "webhook_secret": "empty"},
                }
            ],
        }

        # create a community with the discourse plugin enabled
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

            self.client.put(self.community_url, data=self.community_data, content_type="application/json")

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
                discourse_process_url, data=input_params, content_type="application/json", **self.headers
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

            # call "update" (in prod, would be invoked from celery task)
            from metagov.core.views import get_proxy
            process.plugin = get_proxy(process.plugin)
            process.update()

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

            # call "update" (in prod, would be invoked from celery task)
            process.update()

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
