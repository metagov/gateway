create_conversation = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "raw": {"type": "string"},
        "title": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["raw", "title"],
}

create_comment = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"raw": {"type": "string"}, "conversation_id": {"type": "string"}, "expense_id": {"type": "string"}},
    "required": ["raw"],
}

process_expense = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "expense_id": {"type": "string"},
        "action": {"type": "string", "description": "APPROVE, UNAPPROVE, or REJECT"},
    },
    "required": ["expense_id", "action"],
}

expense_created_event = {"type": "object", "additionalProperties": True, "properties": {"url": {"type": "string"}}}
