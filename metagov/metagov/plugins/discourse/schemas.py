
create_post_parameters = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "raw": {
            "type": "string"
        },
        "topic_id": {
            "type": "integer"
        }
    },
    "required": [
        "raw",
        "topic_id"
    ]
}
create_post_response = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "url": {
            "type": "string"
        }
    },
    "required": [
        "url"
    ]
}