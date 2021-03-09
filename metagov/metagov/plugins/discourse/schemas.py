
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
        },
        "post_number": {
            "type": "integer"
        }
    },
    "required": [
        "url",
        "post_number"
    ]
}

delete_post_parameters = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "post_number": {
            "type": "integer"
        }
    },
    "required": [
        "post_number"
    ]
}