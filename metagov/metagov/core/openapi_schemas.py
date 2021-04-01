from drf_yasg import openapi

community_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        "name": openapi.Schema(type=openapi.TYPE_STRING, description="Unique community slug"),
        "readable_name": openapi.Schema(type=openapi.TYPE_STRING, description="Human-readable community name"),
        "plugins": openapi.Schema(
            type=openapi.TYPE_ARRAY,
            description="List of activated plugins and their configs",
            items=openapi.Items(openapi.TYPE_OBJECT),
        )
        #     openapi.Schema(
        #         type=openapi.TYPE_OBJECT,
        #         properties={
        #             "name": openapi.Schema(
        #                 type=openapi.TYPE_STRING,
        #                 description='plugin name'
        #             ),
        #             "config": openapi.Schema(
        #                 type=openapi.TYPE_OBJECT,
        #                 description='plugin config'
        #             )
        #         }))
        # ),
    },
)

class Tags(object):
    GOVERNANCE_PROCESS = "Governance Processes"
    PUBLIC_ACTION = "Actions (Public)"
    ACTION = "Actions"
    COMMUNITY = "Community Configuration"
