send_message_parameters = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "raw": {"type": "string"},
        "is_warning": {"type": "boolean"},
        "target_usernames": {"type": "array", "items": {"type": "string"}},
        "initiator": {"type": "string"},
    },
    "required": ["title", "raw", "target_usernames"],
}
create_post_parameters = {
    "type": "object",
    "properties": {"raw": {"type": "string"}, "topic_id": {"type": "integer"}, "initiator": {"type": "string"}},
    "required": ["raw", "topic_id"],
}
create_topic_parameters = {
    "type": "object",
    "properties": {
        "raw": {"type": "string"},
        "category": {"type": "integer"},
        "title": {"type": "string"},
        "initiator": {"type": "string"},
    },
    "required": ["raw", "title", "category"],
}
create_post_or_topic_response = {
    "type": "object",
    "properties": {"url": {"type": "string"}, "post_id": {"type": "integer"}, "topic_id": {"type": "integer"}},
    "required": ["url", "post_id", "topic_id"],
}
delete_post_or_topic_parameters = {
    "type": "object",
    "properties": {"id": {"type": "integer"}},
    "required": ["id"],
}
lock_post_parameters = {
    "type": "object",
    "properties": {"id": {"type": "integer"}, "locked": {"type": "boolean"}},
    "required": ["id", "locked"],
}
lock_post_response = {"type": "object", "properties": {"locked": {"type": "boolean"}}}

post_topic_created_event = {
    "type": "object",
    "additionalProperties": True,
    "properties": {"id": {"type": "integer"}, "url": {"type": "string"}},
}
