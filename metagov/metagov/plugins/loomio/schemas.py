# options from https://www.loomio.org/help/api?api_key=undefined
start_loomio_poll = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "title of the thread"},
        "closing_at": {"type": "string", "format": "date"},
        "subgroup": {
            "type": "string",
            "description": "subgroup to create the poll in. can be the loomio key or the loomio handle. only works if plugin is configured with an API key for this subgroup.",
        },
        "poll_type": {
            "type": "string",
            "enum": ["proposal", "poll", "count", "score", "ranked_choice", "meeting", "dot_vote"],
            "description": "the voting style of the poll",
        },
        "details": {"type": "string", "description": "the main text of the poll"},
        "details_format": {
            "type": "string",
            "enum": ["html", "md"],
        },
        "specified_voters_only": {
            "type": "boolean",
            "description": "if true, only invited people can vote, if false, anyone in the group or thread can vote",
        },
        "hide_results_until_closed": {
            "type": "boolean",
            "description": "allow voters to see the results before the poll has closed",
        },
        "anonymous": {"type": "boolean", "description": "hide identities of voters"},
        "discussion_id": {"type": "number", "description": "id of discussion thread to add this poll to"},
        "voter_can_add_options": {"type": "boolean", "description": "if voters can add options to the poll"},
        "recipient_audience": {
            "type": "string",
            "description": "'group' or null. if 'group' whole group will be notified about the new thread",
        },
        "notify_on_closing_soon": {
            "type": "string",
            "enum": ["nobody", "author", "undecided_voters", "voters"],
            "description": "audience to send a reminder notification to, 24 hours before the poll closes",
        },
        "options": {
            "type": "array",
            "items": {"type": "string"},
            "description": "when proposal then agree, disagree, abstain, block. when meeting then a iso8601 date or datetime. otherwise it's anything goes.",
        },
        "recipient_user_ids": {
            "type": "array",
            "description": "array of user ids to notify or invite",
            "items": {"type": "number"},
        },
        "recipient_emails": {
            "type": "array",
            "description": "array of email addresses of people to invite to the thread",
            "items": {"type": "string"},
        },
        "recipient_message": {"type": "string", "description": "message to include in the email invitation"},
    },
    "required": ["title", "options", "closing_at", "poll_type"],
}


create_discussion_input = {
    "type": "object",
    "properties": {
        "subgroup": {
            "type": "string",
            "description": "subgroup to create the discussion in. can be the loomio key or the loomio handle. only works if plugin is configured with an API key for this subgroup.",
        },
        "title": {"type": "string", "description": "title of the thread"},
        "description": {"type": "string", "description": "context for the thread"},
        "description_format": {
            "type": "string",
            "enum": ["html", "md"],
        },
        "recipient_audience": {
            "type": "string",
            "description": "'group' or null. if 'group' whole group will be notified about the new thread",
        },
        "recipient_user_ids": {
            "type": "array",
            "description": "array of user ids to notify or invite",
            "items": {"type": "string"},
        },
        "recipient_emails": {
            "type": "array",
            "description": "array of email addresses of people to invite to the thread",
            "items": {"type": "string"},
        },
        "recipient_message": {"type": "string", "description": "message to include in the email invitation"},
    },
    "required": ["title"],
}
