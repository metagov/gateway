import jsonschema
from django.db import IntegrityError
from django.test import TestCase
from metagov.core.app import MetagovApp
from metagov.core.handlers import MetagovRequestHandler
from metagov.core.signals import governance_process_updated
from .plugin_test_utils import catch_signal

TEST_SLUG = "xyz"


class MetagovAppCreateCommunityTests(TestCase):
    def setUp(self):
        self.app = MetagovApp()

    def test_create_community(self):
        community = self.app.create_community(readable_name="my community")
        self.assertIsNotNone(community.slug)
        self.assertEqual(community.readable_name, "my community")
        self.assertEqual(self.app.get_community(community.slug), community)

    def test_create_community_custom_slug(self):
        community = self.app.create_community(slug="xyz")
        self.assertEqual(community.slug, "xyz")

        # duplicated slugs raise exception
        with self.assertRaises(IntegrityError) as context:
            self.app.create_community(slug=TEST_SLUG)
        self.assertTrue("unique constraint failed" in str(context.exception).lower())


class MetagovAppTests(TestCase):
    def setUp(self):
        self.app = MetagovApp()
        self.app.create_community(slug="xyz")

    def test_manage_plugins(self):
        community = self.app.get_community(slug=TEST_SLUG)

        # it does validation
        with self.assertRaises(jsonschema.exceptions.ValidationError) as context:
            community.enable_plugin("randomness")

        # can enable plugin
        community.enable_plugin("randomness", {"default_low": 10, "default_high": 100})

        # get_plugin returns the proxy instance so we can access methods on it
        plugin = community.get_plugin("randomness")
        plugin.rand_int()

        # can run process
        process = plugin.start_process("delayed-stochastic-vote", options=["one", "two"], delay=0)
        self.assertEqual(process.status, "pending")

        # get_process returns proxy
        retrieved_process = plugin.get_process(id=process.pk)

        # close() ends the process and emits a signal
        with catch_signal(governance_process_updated) as handler:
            retrieved_process.close()
            handler.assert_called_once()
            kwargs = handler.call_args.kwargs
            self.assertEqual(kwargs["status"], "completed")
            self.assertIsNotNone(kwargs["outcome"]["winner"])

        self.assertEqual(retrieved_process.status, "completed")

        # can disable plugin
        community.disable_plugin("randomness")

        self.assertEqual(community.plugins.count(), 0)


class MetagovRequestHandlerTests(TestCase):
    def setUp(self):
        self.app = MetagovApp()
        self.app.create_community(slug="xyz")
        self.handler = MetagovRequestHandler(self.app)

    def test_request_handler(self):
        handler = self.handler._get_plugin_request_handler("slack")
        self.assertIsNotNone(handler)

        handler = self.handler._get_plugin_request_handler("sourcecred")
        self.assertIsNone(handler)
