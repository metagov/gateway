from contextlib import suppress
from enum import Enum

import json, random
from django.db import models, ValueError, IntegrityError

from metagov.core.models import MetagovID, LinkedAccount


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
            raise ValueError(
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
