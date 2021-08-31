from contextlib import suppress
from enum import Enum

import json, random
from django.db import models, IntegrityError

from metagov.core.models import Community


class MetagovID(models.Model):
    """Metagov ID table links all public_ids to a single internal representation of a user. When data
    associated with public_ids conflicts, primary_ID is used.

    Fields:

    community: foreign key - metagov community the user is part of
    internal_id: integer - unique, secret ID
    public_ids: list of integers - public IDs shared with Driver, callers, etc. must have at least one item
    primary_id: integer - used to resolve conflicts if there are multiple public_ids associated with a user

    FIXME: I don't like that linked_accounts links to this model as metagov_id but it's actually
    linking to one of the public_ids (which, admittedly should resolve to a single metagov_id)"""

    community = models.ForeignKey(Community)
    internal_id = models.PositiveIntegerField(unique=True)
    public_ids = models.JSONField(default=list)
    primary_id = models.PositiveIntegerField(unique=True)

    # Internal logic

    def add_id(self, new_id):
        if not self.public_ids:
            self.primary_id = new_id
        self.public_ids.append(new_id)

    def change_primary_id(self, new_primary_id):
        if new_primary_id not in self.public_ids:
            raise ValueError(f"New primary_id {new_primary_id} not in public IDs")
        self.primary_id = new_primary_id


class LinkType(Enum):
    OAUTH = "oauth"
    MANUAL_ADMIN = "manual admin"
    EMAIL_MATCHING = "email matching"
    UNKNOWN = "unknown"


class LinkQuality(Enum):
    STRONG_CONFIRM = "confirmed (strong)"
    WEAK_CONFIRM = "confirmed (weak)"
    UNCONFIRMED = "unconfirmed"
    UNKNOWN = "unknown"


class LinkedAccounts(models.Model):
    """Contains information about specific platform account linked to user

    Fields:

    metagov_id: integer - must match ID in public_ids col of a row in metagov_IDs table
    community: foreign key - metagov community the user is part of
    community_platform_id: string (optional) - distinguishes between ie two Slacks in the same community
    platform_type: string - ie Github, Slack
    platform_identifier: string - ID, username, etc, unique to the platform (or unique to community_platform_id)
    custom_data: dict- optional additional data for linked platform account
    link_type: string (choice) - method through which account was linked
    link_quality: string (choice) - metagov's assessment of the quality of the link (depends on method)
   """

    metagov_id = models.PositiveBigIntegerField()
    community = models.ForeignKey(Community)
    community_platform_id = models.CharField(max_length=100, blank=True, null=True)
    platform_type = models.CharField(max_length=50)
    platform_identifier = models.CharField(max_length=200)

    custom_data = models.JSONField(default=dict)
    link_type = models.CharField(max_length=30, choices=[(t.value, t.name) for t in LinkType],
        default=LinkType.UNKNOWN.value)
    link_quality = models.CharField(max_length=30, choices=[(q.value, q.name) for q in LinkQuality],
        default=LinkQuality.UNKNOWN.value)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=['community', 'community_platform_id', 'platform_type', 'platform_identifier'],
                name='unique_identifer_on_community_platform')
        ]

    def serialize(self):
        return {"metagov_id": self.metagov_id, "community": self.community.slug,
            "community_platform_id": self.community_platform_id, "platform_type": self.platform_type,
            "platform_identifier": self.platform_identifier, "custom_data": self.custom_data,
            "link_type": self.link_type, "link_quality": self.link_quality}


class IdentityAPI(object):

    # Account Management

    def create(self, count=1):
        """Creates new MetagovID instances and returns their associated primary_IDs in a list.
        Creates one instance by default but can create any number at once through count parameter."""

        ids_created = []

        while len(ids_created) < count:
            internal_id = random.random(0, 2147483647)
            public_id = random.random(0, 2147483647)
            try:
                MetagovID.objects.create(internal_id=internal_id, public_ids=[public_id], primary_id=public_id)
                ids_created.append(public_id)
            except IntegrityError as error:
                # if uniqueness error, ignore and try again, otherwise re-raise the error
                if 'UNIQUE constraint' not in str(e.args):
                    raise error

        return ids_created

    def merge(self, primary_instance_id, secondary_instance_id):
        """Merges two MetagovID objects given their associated primary_ids. Saves secondary_instance_id
        to public_ids of primary_instance and deletes secondary_instance."""
        primary_instance = MetagovID.objects.get(primary_id=primary_instance_id)
        secondary_instance = MetagovID.objects.get(primary_id=secondary_instance_id)
        primary_instance.add_id(secondary_instance_id)
        primary_instance.save()
        secondary_instance.delete()

    def validate_metagov_id(self, metagov_id):
        """Helper method which confirms that a metagov_id is contained in the public_ids of a MetagovID
        instance."""
        return bool(MetagovID.objects.filter(public_ids__contains=[metagov_id]))

    def link(self, metagov_id, community, platform_type, platform_identifier, community_platform_id=None,
        custom_data=None, link_type=None, link_quality=None):
        """Links a new platform account to an existing user, as specified by their metagov_id."""

        if not self.validate_metagov_id(metagov_id):
            raise ValidationError(f"metagov_id {metagov_id} was not found in database.")

        account = LinkedAccounts(metagov_id=metagov_id, community=community,
            platform_type=platform_type, platform_identifier=platform_identifier)
        if community_platform_id:
            account.community_platform_id = community_platform_id
        if custom_data:
            account.custom_data = custom_data
        if link_type:
            account.link_type = link_type
        if link_quality:
            account.link_quality = link_quality
        account.save()

        return account

    def unlink(self, community, platform_type, platform_identifier, community_platform_id=None):
        """Unlinks a platform account from a metagov user."""

        result = MetagovID.objects.filter(community=community, platform_type=platform_type,
            platform_identifier=platform_identifier)
        if community_platform_id:
            result = result.filter(community_platform_id=community_platform_id)
        if not result:
            return False  # FIXME: should we raise an error here instead?
        result.delete()
        return True

    # Data Retrieval

    def get_filters(self, platform_type, community_platform_id, link_type, link_quality):
        """Helper function to filter by keys only when value is not None."""
        filters = {"platform_type": platform_type, "community_platform_id": community_platform_id,
            "link_type": link_type, "link_quality": link_quality}
        return {key: val for key, val in filters.items() if val is not None}

    def get_identity_data_object(self, metagov_id_instance):
        """Helper function, takes a MetagovID object instance and creates a json dictionary for its
        data plus all linked LinkedAccount objects."""
        linked_accounts = []
        for public_id in metagov_id_instance.public_ids:
            for account in LinkedAccounts.objects.filter(metagov_id=public_id, community=community):
                linked_accounts.append(account.serialize())
        return {
            "primary_id": metagov_id_instance.primary_id,
            "public_ids": [metagov_id_instance.public_ids],
            "linked_accounts": linked_accounts
        }

    def get_user(self, metagov_id):
        """Get a user given metagov_id, returned as Identity Data Object."""
        instance = MetagovID.objects.filter(public_ids__contains=[metagov_id])[0]
        return self.get_identity_data_object(instance)

    def get_users(self, community, platform_type=None, community_platform_id=None,
        link_type=None, link_quality=None):
        """Gets all users in a given community. Supply platform type and/or ID, link_type and/or
        link_quality for further filtering."""

        users = []

        # get linked accounts, filter further if needed
        results = LinkedAccounts.objects.filter(community=community)
        filters = self.get_filters(platform_type, community_platform_id, link_type, link_quality)
        results = results.filter(filters) if filters else results

        # get metagov_ids associated with linked accounts and use them to generate identity data objects
        for result in results:
            id_instances = MetagovID.objects.filter(public_ids__contains=[result.metagov_id])
            users.append(id_instances[0])  # should always be exactly one match, so [0] should work
        return [self.get_identity_data_object(user) for user in users]

    def filter_users_by_account(self, metagov_id_list, platform_type=None, community_platform_id=None,
        link_type=None, link_quality=None):
        """Given a list of users specified via metagov_id, filters to only those containing at least
        one linked account matching the given criteria.

        FIXME: don't we want to highlight the matching linked account somehow?
        """

        # get user id objects
        users = []
        for metagov_id in metagov_id_list:
            users.append(MetagovID.objects.filter(public_ids__contains=[result.metagov_id])[0])

        # filter
        filtered_users = []
        filters = self.get_filters(platform_type, community_platform_id, link_type, link_quality)
        for user in users:
            if user.linked_accounts.filter(filters):
                filtered_users.append(self.get_identity_data_object(user))
        return filtered_users

    def get_linked_account(self, metagov_id, platform_type, community_platform_id=None):
        """Given a metagov_id and platform_type, get a linked account if it exists."""
        id_instance = MetagovID.objects.filter(public_ids__contains=[metagov_id])[0]
        for account in id_instance.linked_accounts:
            if account.platform_type == platform_type:
                if not community_platform_id or account.community_platform_id == community_platform_id:
                    return account.serialize()
        return None
