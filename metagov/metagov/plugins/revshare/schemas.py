pointer_and_weight = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"pointer": {"type": "string"}, "weight": {"type": "integer"}},
    "required": ["pointer", "weight"],
}
pointer = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"pointer": {"type": "string"}},
    "required": ["pointer"],
}

pointers = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"pointers": {"type": "object"}},
    "required": ["pointers"],
}

discourse_pick_pointer_input = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"topic_id": {"type": "integer"}},
    "required": ["topic_id"],
}

lock_post_parameters = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"id": {"type": "integer"}, "locked": {"type": "boolean"}},
    "required": ["id", "locked"],
}
lock_post_response = {"type": "object", "additionalProperties": False, "properties": {"locked": {"type": "boolean"}}}
