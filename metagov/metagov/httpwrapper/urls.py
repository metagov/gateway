from django.conf.urls import url
from django.urls import include, path

from metagov.core import utils
from metagov.httpwrapper import views, utils
from metagov.httpwrapper import identity as identity_views
from metagov.core.plugin_manager import plugin_registry


management_patterns = [

    # Create a new community
    path(f"{utils.internal_path}/community", views.create_community, name="community"),
    # Get, update, or delete a community
    path(f"{utils.internal_path}/community/<slug:slug>", views.community, name="community"),

    # Disable plugin
    path(f"{utils.internal_path}/plugin/<slug:plugin_name>/<int:id>", views.delete_plugin, name="delete_plugin"),
    # initiate an authorization flow defined in a plugin. results in a redirect to obtain consent from the user.
    path("auth/<slug:plugin_name>/authorize", views.plugin_authorize, name="plugin_authorize"),

]


identity_patterns = [

    path(f"{utils.internal_path}/identity/create_id", identity_views.create_id, name="create_id"),
    path(f"{utils.internal_path}/identity/merge_ids", identity_views.merge_ids, name="merge_ids"),
    path(f"{utils.internal_path}/identity/link_account", identity_views.link_account, name="link_account"),
    path(f"{utils.internal_path}/identity/unlink_account", identity_views.unlink_account, name="unlink_account"),
    path(f"{utils.internal_path}/identity/get_user", identity_views.get_user, name="get_user"),
    path(f"{utils.internal_path}/identity/get_users", identity_views.get_users, name="get_users"),
    path(f"{utils.internal_path}/identity/filter_users_by_account", identity_views.filter_users_by_account,
        name="filter_users_by_account"),
    path(f"{utils.internal_path}/identity/get_linked_account", identity_views.get_linked_account, name="get_linked_account"),

]


plugin_patterns = []

for (key, cls) in plugin_registry.items():
    enable_plugin_view = views.decorated_enable_plugin_view(cls.name)
    plugin_patterns.append(path(f"{utils.internal_path}/plugin/{cls.name}", enable_plugin_view))

    for (slug, meta) in cls._action_registry.items():
        # Add view for action endpoint
        route = utils.construct_action_url(cls.name, slug)
        view = views.decorated_perform_action_view(cls.name, slug)
        plugin_patterns.append(path(route, view))

        # If action is PUBLIC, add a second endpoint (keep "internal" path for Driver's convenience)
        if meta.is_public:
            route = utils.construct_action_url(cls.name, slug, is_public=True)
            view = views.decorated_perform_action_view(cls.name, slug, tags=[Tags.PUBLIC_ACTION])
            plugin_patterns.append(path(route, view))

    for (slug, process_cls) in cls._process_registry.items():
        # Add view for starting a governance process (POST)
        route = utils.construct_process_url(cls.name, slug)
        view = views.decorated_create_process_view(cls.name, slug)
        plugin_patterns.append(path(route, view))

        # Add view for checking (GET) and closing (DELETE) a governance process
        view = views.decorated_get_process_view(cls.name, slug)
        plugin_patterns.append(path(f"{route}/<int:process_id>", view))