post_with_open_poll = {
    "id": 1,
    "polls": [
        {
            "name": "poll",
            "type": "regular",
            "status": "open",
            "results": "always",
            "options": [
                {"id": "d8166958d0c9b9f5917456ef69a404c2", "html": "one", "votes": 0},
                {"id": "6eaceb40c21dfe95cc8e17f801152174", "html": "two", "votes": 0},
                {"id": "b92738ba6c1dbbc9bffabd806f87fc96", "html": "three", "votes": 0},
            ],
            "voters": 0,
        }
    ],
}
post_with_open_poll_and_votes = {
    "id": 1,
    "polls": [
        {
            "name": "poll",
            "type": "regular",
            "status": "open",
            "results": "always",
            "options": [
                {"id": "d8166958d0c9b9f5917456ef69a404c2", "html": "one", "votes": 10},
                {"id": "6eaceb40c21dfe95cc8e17f801152174", "html": "two", "votes": 15},
                {"id": "b92738ba6c1dbbc9bffabd806f87fc96", "html": "three", "votes": 25},
            ],
            "voters": 50,
        }
    ],
}
post_with_closed_poll_and_votes = {
    "id": 1,
    "polls": [
        {
            "name": "poll",
            "type": "regular",
            "status": "closed",
            "results": "always",
            "options": [
                {"id": "d8166958d0c9b9f5917456ef69a404c2", "html": "one", "votes": 10},
                {"id": "6eaceb40c21dfe95cc8e17f801152174", "html": "two", "votes": 15},
                {"id": "b92738ba6c1dbbc9bffabd806f87fc96", "html": "three", "votes": 35},
            ],
            "voters": 60,
        }
    ],
}

toggle_response_closed = {
    "poll": {
        "name": "poll",
        "type": "regular",
        "status": "closed",
        "results": "always",
        "options": [
            {"id": "d8166958d0c9b9f5917456ef69a404c2", "html": "one", "votes": 10},
            {"id": "6eaceb40c21dfe95cc8e17f801152174", "html": "two", "votes": 15},
            {"id": "b92738ba6c1dbbc9bffabd806f87fc96", "html": "three", "votes": 35},
        ],
        "voters": 60,
    }
}
