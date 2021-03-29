create_post_parameters = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"raw": {"type": "string"}, "topic_id": {"type": "integer"}},
    "required": ["raw", "topic_id"],
}
create_post_response = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"url": {"type": "string"}, "id": {"type": "integer"}},
    "required": ["url", "id"],
}

delete_post_parameters = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"id": {"type": "integer"}},
    "required": ["id"],
}

lock_post_parameters = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"id": {"type": "integer"}, "locked": {"type": "boolean"}},
    "required": ["id", "locked"],
}
lock_post_response = {"type": "object", "additionalProperties": False, "properties": {"locked": {"type": "boolean"}}}
