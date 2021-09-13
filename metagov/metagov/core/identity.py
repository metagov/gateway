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
    external_id: integer - unique, public ID
    linked_ids: many2many - metagovIDs that a given ID has been merged with
    primary: boolean - used to resolve conflicts between linked MetagovIDs."""

    community = models.ForeignKey(Community)
    internal_id = models.PositiveIntegerField(unique=True)
    external_id = models.PositiveIntegerField(unique=True)
    linked_ids = models.ManyToManyField('self')
    primary = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        """Performs extra validation such that if there are linked IDs, only one should have primary set as True."""
        if self.linked_ids:
            true_count = sum(self.primary + [linked_id.primary for linked_id in self.linked_ids])
            if true_count == 0:
                raise IntegrityError("At least one linked ID must have 'primary' attribute set to True.")
            if true_count > 1:
                raise IntegrityError("More than one linked ID has 'primary' attribute set to True.")
        super(MetagovID, self).save(*args, **kwargs)

    def is_primary(self):
        """Helper method to determine if a MetagovID is primary. Accounts for the fact that a MetagovID
        with no linked IDs is primary, even if its primary attribute is set to False."""
        if self.primary or not self.linked_ids:
            return True
        return False


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


class LinkedAccount(models.Model):
    """Contains information about specific platform account linked to user

    Fields:

    metagov_id: foreign key to MetagovID
    community: foreign key - metagov community the user is part of
    community_platform_id: string (optional) - distinguishes between ie two Slacks in the same community
    platform_type: string - ie Github, Slack
    platform_identifier: string - ID, username, etc, unique to the platform (or unique to community_platform_id)
    custom_data: dict- optional additional data for linked platform account
    link_type: string (choice) - method through which account was linked
    link_quality: string (choice) - metagov's assessment of the quality of the link (depends on method)
   """

    metagov_id = models.ForeignKey(MetagovID, related_name="linked_accounts")
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
        return {"external_id": self.metagov_id.external_id, "community": self.community.slug,
            "community_platform_id": self.community_platform_id, "platform_type": self.platform_type,
            "platform_identifier": self.platform_identifier, "custom_data": self.custom_data,
            "link_type": self.link_type, "link_quality": self.link_quality}


class IdentityAPI(object):

    # Account Management

    def create(self, community, count=1):
        """Creates new MetagovID instances and returns their associated external_IDs in a list.
        Creates one instance by default but can create any number at once through count parameter."""

        ids_created = []

        while len(ids_created) < count:
            try:
                obj = MetagovID.objects.create(
                    community=community,
                    internal_id=random.random(0, 2147483647),
                    external_id=random.random(0, 2147483647)
                )
                ids_created.append(obj.external_id)
            except IntegrityError as error:
                # if uniqueness error, ignore and try again, otherwise re-raise the error
                if 'UNIQUE constraint' not in str(e.args):
                    raise error

        return ids_created

    def merge(self, primary_instance_id, secondary_instance_id):
        """Merges two MetagovID objects given their associated primary_ids. Adds IDs to each other's
        linked_IDs and turns the boolean of the secondary instance to False."""
        primary_instance = MetagovID.objects.get(primary_id=primary_instance_id)
        secondary_instance = MetagovID.objects.get(primary_id=secondary_instance_id)
        primary_instance.linked_ids.add(secondary_instance)
        secondary_instance.linked_ids.add(primary_instance)
        primary_instance.save()
        secondary_instance.primary = False
        secondary_instance.save()

    def link(self, external_id, community, platform_type, platform_identifier, community_platform_id=None,
        custom_data=None, link_type=None, link_quality=None):
        """Links a new platform account to an existing user, as specified by their external metagov id."""

        metagovID = MetagovID.objects.get(external_id=external_id)

        account = LinkedAccount(metagov_id=metagovID, community=community,
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
        """Unlinks a platform account from a metagov user. Uses community & platform information
        which should be, together, unique to a metagovID."""

        result = LinkedAccount.objects.filter(community=community, platform_type=platform_type,
            platform_identifier=platform_identifier)
        if community_platform_id:
            result = result.filter(community_platform_id=community_platform_id)
        if not result:
            raise IntegrityError(
                f"No LinkedAccount found in community {community} with platform {platform_type} "
                f"and identifier {platform_identifier} (community_platform_id: {community_platform_id})"
            )
        result[0].delete()
        return True

    # Data Retrieval

    def get_filters(self, platform_type, community_platform_id, link_type, link_quality):
        """Helper function to filter by keys only when value is not None."""
        filters = {"platform_type": platform_type, "community_platform_id": community_platform_id,
            "link_type": link_type, "link_quality": link_quality}
        return {key: val for key, val in filters.items() if val is not None}

    def get_identity_data_object(self, metagovID):
        """Helper function, takes a MetagovID object instance and creates a json dictionary for its
        data plus all linked LinkedAccount objects."""
        linked_accounts = []
        primary_ID = None
        for mID in metagovID + metagovID.linked_IDs:
            for account in LinkedAccount.objects.filter(metagov_id=mID):
                linked_accounts.append(account.serialize())
                if mID.primary = True:
                    primary = mID.external_id
        return {
            "source_ID": metagovID.external_id,
            "primary_ID": primary_ID,
            "linked_accounts": linked_accounts
        }

    def get_user(self, external_id):
        """Get a user given external_id, returned as Identity Data Object."""
        instance = MetagovID.objects.filter(external_id=external_id)
        return self.get_identity_data_object(instance)

    def get_users(self, community, platform_type=None, community_platform_id=None,
        link_type=None, link_quality=None):
        """Gets all users in a given community. Supply platform type and/or ID, link_type and/or
        link_quality for further filtering."""

        # get linked accounts, filter further if needed
        results = LinkedAccount.objects.filter(community=community)
        filters = self.get_filters(platform_type, community_platform_id, link_type, link_quality)
        results = results.filter(filters) if filters else results

        # get metagov_ids associated with linked accounts and use them to generate identity data objects
        users = set([])
        for result in results:
            users.add(result.metagov_id)
        return [self.get_identity_data_object(user) for user in users]

    def filter_users_by_account(self, external_id_list, platform_type=None, community_platform_id=None,
        link_type=None, link_quality=None):
        """Given a list of users specified via external_id, filters to only those containing at least
        one linked account matching the given criteria."""

        # get user id objects
        users = []
        for external_id in external_id_list:
            users.append(MetagovID.objects.get(external_id=external_id)

        # filter
        filtered_users = []
        filters = self.get_filters(platform_type, community_platform_id, link_type, link_quality)
        for user in users:
            if user.linked_accounts.filter(filters):
                filtered_users.append(self.get_identity_data_object(user))
        return filtered_users

    def get_linked_account(self, external_id, platform_type, community_platform_id=None):
        """Given a metagov_id and platform_type, get a linked account if it exists."""
        id_instance = MetagovID.objects.get(external_id=external_id)
        for account in id_instance.linked_accounts:
            if account.platform_type == platform_type:
                if not community_platform_id or account.community_platform_id == community_platform_id:
                    return account.serialize()
        return None
