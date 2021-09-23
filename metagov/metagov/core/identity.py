from contextlib import suppress
from enum import Enum
import json, random
from django.db import models, IntegrityError
from metagov.core.models import MetagovID, LinkedAccount


# Account Management

def create_id(community, count=1):
    """Creates new MetagovID instances and returns their associated external_IDs in a list.
    Creates one instance by default but can create any number at once through count parameter."""

    ids_created = []

    while len(ids_created) < count:
        try:
            obj = MetagovID.objects.create(
                community=community,
                internal_id=random.randint(0, 2147483647),
                external_id=random.randint(0, 2147483647)
            )
            ids_created.append(obj.external_id)
        except IntegrityError as error:
            # if uniqueness error, ignore and try again, otherwise re-raise the error
            if 'UNIQUE constraint' not in str(e.args):
                raise error

    return ids_created

def merge_ids(primary_instance_id, secondary_instance_id):
    """Merges two MetagovID objects given their associated external_ids. Adds IDs to each other's
    linked_IDs and turns the boolean of the secondary instance to False."""
    primary_instance = MetagovID.objects.get(external_id=primary_instance_id)
    secondary_instance = MetagovID.objects.get(external_id=secondary_instance_id)
    secondary_instance.linked_ids.add(primary_instance)
    secondary_instance.primary = False
    secondary_instance.save()
    primary_instance.linked_ids.add(secondary_instance)
    primary_instance.save()

def link_account(external_id, community, platform_type, platform_identifier, community_platform_id=None,
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

def retrieve_account(community, platform_type, platform_identifier, blah, community_platform_id=None):
    """Helper method to get a specific linked account."""
    result = LinkedAccount.objects.filter(community=community, platform_type=platform_type,
        platform_identifier=platform_identifier)
    if community_platform_id:
        result = result.filter(community_platform_id=community_platform_id)
    if not result:
        raise ValueError(
            f"No LinkedAccount found in community {community} with platform {platform_type} "
            f"and identifier {platform_identifier} (community_platform_id: {community_platform_id})"
        )
    return result[0]

def update_linked_account(community, platform_type, platform_identifier, community_platform_id=None,
    custom_data=None, link_type=None, link_quality=None):
    """Links a new platform account to an existing user, as specified by their external metagov id."""

    account = retrieve_account(community, platform_type, platform_identifier, community_platform_id)

    if custom_data:
        account.custom_data = custom_data
    if link_type:
        account.link_type = link_type
    if link_quality:
        account.link_quality = link_quality
    account.save()

    return account

def unlink_account(community, platform_type, platform_identifier, community_platform_id=None):
    """Unlinks a platform account from a metagov user. Uses community & platform information
    which should be, together, unique to a metagovID.

    FIXME: return something else here - the metagov identity data object without the linked account??"""

    result = retrieve_account(community, platform_type, platform_identifier, community_platform_id)
    result.delete()
    return True

# Data Retrieval

def strip_null_values_from_dict(dictionary):
    return {key: val for key, val in dictionary.items() if val is not None}

def get_filters(platform_type, community_platform_id, link_type, link_quality):
    """Helper function to filter by keys only when value is not None."""
    filters = {"platform_type": platform_type, "community_platform_id": community_platform_id,
        "link_type": link_type, "link_quality": link_quality}
    return strip_null_values_from_dict(filters)

def get_identity_data_object(metagovID):
    """Helper function, takes a MetagovID object instance and creates a json dictionary for its
    data plus all linked LinkedAccount objects."""
    linked_accounts = []
    primary_id = None
    ids_to_check = set([metagovID])
    ids_checked = set([])
    while len(ids_to_check) > 0:
        current_id = ids_to_check.pop()
        # get any linked_ids not already checked
        for linked_id in current_id.linked_ids.all():
            if linked_id not in ids_checked:
                ids_to_check.add(linked_id)
        # get and serialized linked accounts for current ID
        for account in LinkedAccount.objects.filter(metagov_id=current_id):
            linked_accounts.append(account.serialize())
        # record if primary, and that it was checked
        if current_id.primary == True:
                primary_id = current_id.external_id
        ids_checked.add(current_id)
    return {
        "source_ID": metagovID.external_id,
        "primary_ID": primary_id,
        "linked_accounts": linked_accounts
    }

def get_user(external_id):
    """Get a user given external_id, returned as Identity Data Object."""
    instance = MetagovID.objects.get(external_id=external_id)
    return get_identity_data_object(instance)

def get_users(community, platform_type=None, community_platform_id=None,
    link_type=None, link_quality=None):
    """Gets all users in a given community. Supply platform type and/or ID, link_type and/or
    link_quality to filter."""

    if platform_type or community_platform_id or link_type or link_quality:

        # get linked accounts & filter
        results = LinkedAccount.objects.filter(community=community)
        filters = get_filters(platform_type, community_platform_id, link_type, link_quality)
        results = results.filter(**filters) if filters else results

        # get metagov_ids associated with linked accounts, removing duplicates by using primary ID
        users = set([])
        for result in results:
            users.add(result.metagov_id.get_primary_id())

    else:

        users = MetagovID.objects.filter(community=community, primary=True)

    return [get_identity_data_object(user) for user in users]

def filter_users_by_account(external_id_list, platform_type=None, community_platform_id=None,
    link_type=None, link_quality=None):
    """Given a list of users specified via external_id, filters to only those containing at least
    one linked account matching the given criteria. If no filters passed in, returns all
    users."""

    # get user id objects
    users = []
    for external_id in external_id_list:
        users.append(MetagovID.objects.get(external_id=external_id))

    # filter
    filtered_users = []
    filters = get_filters(platform_type, community_platform_id, link_type, link_quality)
    for user in users:
        if not filters or user.linked_accounts.filter(**filters):
            filtered_users.append(get_identity_data_object(user))
    return filtered_users

def get_linked_account(external_id, platform_type, community_platform_id=None):
    """Given a metagov_id and platform_type, get a linked account if it exists."""
    id_instance = MetagovID.objects.get(external_id=external_id)
    for account in id_instance.linked_accounts.all():
        if account.platform_type == platform_type:
            if not community_platform_id or account.community_platform_id == community_platform_id:
                return account.serialize()
    return {}
