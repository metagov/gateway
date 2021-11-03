from metagov.core.models import Community


class MetagovApp:
    def __init__(self):
        pass

    @property
    def communities(self):
        return Community.objects.all()

    def get_community(self, slug) -> Community:
        return Community.objects.get(slug=slug)

    def create_community(self, readable_name="", slug=None) -> Community:
        if slug:
            return Community.objects.create(slug=slug, readable_name=readable_name)
        return Community.objects.create(readable_name=readable_name)
