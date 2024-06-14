internal_path = "api/internal"  # FIXME: should this be defined in settings?


def construct_action_url(plugin_name: str, slug: str, is_public=False) -> str:
    if is_public:
        return f"api/action/{plugin_name}.{slug}"
    return f"{internal_path}/action/{plugin_name}.{slug}"


def construct_process_url(plugin_name: str, slug: str) -> str:
    return f"{internal_path}/process/{plugin_name}.{slug}"


def get_driver(**kwargs):
    """Get Driver object given various inputs."""
    from metagov.core.models import Community
    from httpwrapper.models import Driver, CommunityDriverLink, APIKey
    if "driver_instance" in **kwargs:
        return kwargs.get("driver_instance")
    if "driver_slug" in **kwargs:
        return Driver.objects.get(slug=kwargs.get("driver_slug"))
    if "api_key" in **kwargs:
        api_key_object = APIKey.objects.get(key=kwargs.get("api_key"))
        return api_key_object.driver
    if "community" in **kwargs:
        community_driver_link = CommunityDriverLink.objects.get(community=community)
        return community_driver_link.driver
    if "community_slug" in **kwargs:
        community = Community.objects.get(slug=kwargs.get("community_slug"))
        community_driver_link = CommunityDriverLink.objects.get(community=community)
        return community_driver_link.driver


def get_configuration(config_name, **kwargs):
    """We look up configurations based on Driver ID. This function checks for a variety of inputs in
    kwargs that can be uniquely linked to Driver ID before giving up."""
    from httpwrapper.models import DriverConfig
    driver = get_driver(**kwargs)
    if driver:
        return DriverConfig.objects.get(driver=driver, config_name=config_name)
    from metagov.settings import TESTING
    return TESTING if TESTING else None


def set_configuration(config_name, config_value, **kwargs):
    """For a given driver, looks up a config variable name. If a row already exists, update the value,
    otherwise create the row."""
    from httpwrapper.models import DriverConfig
    driver = get_driver(**kwargs)
    if driver:
        driver_config = DriverConfig.objects.get(driver=driver, config_name=config_name)
        if driver_config:
            driver_config.config_value = config_value
            driver_config.save()
        else:
            DriverConfig.objects.create(driver=driver, config_name=config_name, config_value=config_value)