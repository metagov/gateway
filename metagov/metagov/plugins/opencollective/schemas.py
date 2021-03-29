create_conversation_parameters = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"raw": {"type": "string"}, "title": {"type": "string"}},
    "required": ["raw", "title"],
}
create_conversation_response = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "url": {"type": "string"},
        "conversation_id": {"type": "string"},
    },
    "required": ["url", "conversation_id"],
}

create_comment_parameters = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"raw": {"type": "string"}, "conversation_id": {"type": "string"}},
    "required": ["raw", "conversation_id"],
}
create_comment_response = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"comment_id": {"type": "string"}},
    "required": ["comment_id"],
}
