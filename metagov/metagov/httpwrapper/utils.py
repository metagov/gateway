internal_path = "api/internal"  # FIXME: should this be defined in settings?


def construct_action_url(plugin_name: str, slug: str, is_public=False) -> str:
    if is_public:
        return f"api/action/{plugin_name}.{slug}"
    return f"{internal_path}/action/{plugin_name}.{slug}"


def construct_process_url(plugin_name: str, slug: str) -> str:
    return f"{internal_path}/process/{plugin_name}.{slug}"
