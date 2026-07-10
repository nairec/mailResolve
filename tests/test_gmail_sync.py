from src.gmail.sync import extract_message_ids


def test_extract_message_ids_deduplicates() -> None:
    records = [
        {
            "id": "100",
            "messagesAdded": [
                {"message": {"id": "msg-a", "threadId": "t1"}},
                {"message": {"id": "msg-b", "threadId": "t2"}},
            ],
        },
        {
            "id": "101",
            "messagesAdded": [
                {"message": {"id": "msg-a", "threadId": "t1"}},
                {"message": {"id": "msg-c", "threadId": "t3"}},
            ],
        },
    ]

    assert extract_message_ids(records) == ["msg-a", "msg-b", "msg-c"]


def test_extract_message_ids_empty_history() -> None:
    assert extract_message_ids([]) == []
