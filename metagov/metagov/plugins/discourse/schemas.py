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
    "properties": {"url": {"type": "string"}, "id": {"type": "integer"}},
    "required": ["url", "id"],
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
