add_pointer_input = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"pointer": {"type": "string"}, "weight": {"type": "integer"}, "key": {"type": "string"}},
    "required": ["pointer", "weight"],
}
remove_pointer_input = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"pointer": {"type": "string"}, "key": {"type": "string"}},
    "required": ["pointer"],
}
replace_config_input = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"pointers": {"type": "object"}, "key": {"type": "string"}},
    "required": ["pointers"],
}
get_config_input = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"key": {"type": "string"}}
}

pick_pointer_input = get_config_input

pick_pointer_output = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"pointer": {"type": "string"}},
    "required": ["pointer"],
}
