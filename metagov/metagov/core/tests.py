from django.test import TestCase

from metagov.core.models import Community, MetagovID, LinkedAccount, LinkType, LinkQuality
from metagov.core import identity


class MetagovIDManagementTestCase(TestCase):
    """Test functionality related to creating and merging metagovIDs."""

    def setUp(self):

        self.community = Community.objects.create(readable_name="Test Community")

    def test_create_one(self):

        metagov_id = identity.create_id(community=self.community)
        self.assertEqual(len(metagov_id), 1)
        self.assertEqual(type(metagov_id[0]), int)
        self.assertTrue(MetagovID.objects.get(external_id=metagov_id[0]).primary)

    def test_create_many(self):

        metagov_id = identity.create_id(community=self.community, count=5)
        self.assertEqual(len(metagov_id), 5)

    def test_merge(self):

        primary_id = identity.create_id(community=self.community)
        secondary_id = identity.create_id(community=self.community)
        identity.merge_ids(primary_id[0], secondary_id[0])
        primary_inst = MetagovID.objects.get(external_id=primary_id[0])
        secondary_inst = MetagovID.objects.get(external_id=secondary_id[0])

        self.assertTrue(primary_inst.primary)
        self.assertFalse(secondary_inst.primary)
        self.assertEquals(secondary_inst.get_primary_id(), primary_inst)
        self.assertTrue(primary_inst in secondary_inst.linked_ids.all())
        self.assertTrue(secondary_inst in primary_inst.linked_ids.all())


class LinkedAccountManagementTestCase(TestCase):
    """Test functionality related to linking and unlinking accounts."""

    def setUp(self):

        self.community = Community.objects.create(readable_name="Test Community")
        self.external_id = identity.create_id(community=self.community, count=1)[0]

    def test_link(self):

        account = identity.link_account(self.external_id, self.community, "OpenCollective", "crystal_dunn")
        self.assertEquals(account.metagov_id, MetagovID.objects.get(external_id=self.external_id))
        self.assertEquals(account.platform_type, "OpenCollective")
        self.assertEquals(account.platform_identifier, "crystal_dunn")
        self.assertEquals(account.link_type, "unknown")
        self.assertEquals(account.link_quality, "unknown")

        with self.assertRaises(Exception) as context:
            identity.link_account(self.external_id, self.community, "OpenCollective", "crystal_dunn")
        self.assertTrue('LinkedAccount with the following already exists' in str(context.exception))

    def test_unlink(self):

        account = identity.link_account(self.external_id, self.community, "OpenCollective", "crystal_dunn")
        self.assertEquals(LinkedAccount.objects.count(), 1)

        identity.unlink_account(self.community, "OpenCollective", "crystal_dunn")
        self.assertEquals(LinkedAccount.objects.count(), 0)

        account = identity.link_account(self.external_id, self.community, "OpenCollective", "crystal_dunn")
        with self.assertRaises(Exception) as context:
            identity.unlink_account(self.community, "OpenCollective", "megan_rapinoe")
        self.assertTrue('No LinkedAccount found' in str(context.exception))

    def test_update_link(self):

        account = identity.link_account(self.external_id, self.community, "OpenCollective", "crystal_dunn")
        self.assertEquals(account.link_quality, "unknown")
        self.assertEquals(account.link_type, "unknown")

        account = identity.update_linked_account(self.community, "OpenCollective", "crystal_dunn",
            link_quality=LinkQuality.STRONG_CONFIRM, link_type=LinkType.OAUTH)
        self.assertEquals(account.link_quality, LinkQuality.STRONG_CONFIRM)
        self.assertEquals(account.link_type, LinkType.OAUTH)


class DataRetrievalTestCase(TestCase):
    """Test functionality related to retrieving data via the internal API."""

    def setUp(self):

        self.community = Community.objects.create(readable_name="Test Community")
        self.external_id = identity.create_id(community=self.community, count=5)[0]
        self.account = identity.link_account(self.external_id, self.community, "OpenCollective", "crystal_dunn")

    def test_get_identity_data_object(self):

        metagovID = MetagovID.objects.get(external_id=self.external_id)
        self.assertEquals(identity.get_identity_data_object(metagovID), {
            'primary_ID': metagovID.external_id,
            'source_ID': metagovID.external_id,
            'linked_accounts':
                [{
                    'community': str(self.community.slug),
                    'community_platform_id': None,
                    'custom_data': {},
                    'external_id': metagovID.external_id,
                    'link_quality': 'unknown',
                    'link_type': 'unknown',
                    'platform_identifier': 'crystal_dunn',
                    'platform_type': 'OpenCollective'
                }]})

    def test_get_user(self):

        result = identity.get_user(external_id=self.external_id)
        self.assertEquals(result['primary_ID'], self.external_id)
        self.assertEquals(len(result['linked_accounts']), 1)

    def test_get_users(self):

        self.assertEquals(MetagovID.objects.count(), 5)
        result = identity.get_users(self.community)
        self.assertEquals(len(result), 5)

    def test_get_users_with_filters(self):

        account = identity.link_account(MetagovID.objects.last().external_id, self.community, "OpenCollective",
            "tobin_heath", link_type=LinkType.OAUTH)
        result = identity.get_users(self.community, link_type=LinkType.OAUTH, platform_type="OpenCollective")
        self.assertEquals(len(result), 1)
        result = identity.get_users(self.community, platform_type="OpenCollective")
        self.assertEquals(len(result), 2)

    def test_filter_users_by_account(self):
        id_list = [metagov_id.external_id for metagov_id in MetagovID.objects.all()[:3]]
        result = identity.filter_users_by_account(id_list)
        self.assertEquals(len(result), 3)

        matched_id_to_link = MetagovID.objects.all()[0]
        account = identity.link_account(matched_id_to_link.external_id, self.community, "OpenCollective",
            "tobin_heath", link_type=LinkType.OAUTH)
        result = identity.filter_users_by_account(id_list, link_type=LinkType.OAUTH, platform_type="OpenCollective")
        self.assertEquals(len(result), 1)

        unmatched_id_to_link = MetagovID.objects.all()[4]
        account = identity.link_account(unmatched_id_to_link.external_id, self.community, "OpenCollective",
            "midge_purce", link_type=LinkType.OAUTH)
        result = identity.filter_users_by_account(id_list, link_type=LinkType.OAUTH, platform_type="OpenCollective")
        self.assertEquals(len(result), 1)  # note that we still only have one because this user isn't in our ID list

    def test_get_linked_account(self):

        new_id = MetagovID.objects.all()[4]
        account = identity.link_account(new_id.external_id, self.community, "OpenCollective",
            "tobin_heath", link_type=LinkType.OAUTH)
        result = identity.get_linked_account(new_id.external_id, "OpenCollective")
        self.assertEquals(result["platform_type"], "OpenCollective")
        self.assertEquals(result["platform_identifier"], "tobin_heath")
        result = identity.get_linked_account(new_id.external_id, "Slack")
        self.assertEquals(result, {})
