view_parameters = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"method_name": {"type": "string"}, "args": {"type": "object"}},
    "required": ["method_name"],
}
call_parameters = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "method_name": {"type": "string"},
        "args": {"type": "object"},
        "gas": {"type": "number"},
        "amount": {"type": "number"},
    },
    "required": ["method_name"],
}
