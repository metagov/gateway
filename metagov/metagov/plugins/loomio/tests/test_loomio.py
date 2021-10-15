from metagov.plugins.loomio.models import create_vote_dict
from django.test import TestCase
import metagov.plugins.loomio.tests.mocks as LoomioMock


class UnitTests(TestCase):
    def test_vote_dict(self):
        vote_dict = create_vote_dict(LoomioMock.loomio_show_poll_response)
        self.assertDictEqual(
            vote_dict, {"agree": {"count": 1, "users": ["879750"]}, "disagree": {"count": 0, "users": []}}
        )
