from chatnec.models import UniversalMessage, UniversalReply


def test_reply_to_inherits_addressing():
    msg = UniversalMessage(
        platform="slack",
        chat_id="C123",
        thread_id="T456",
        user_id="U789",
        text="hello",
    )
    reply = UniversalReply.to(msg, text="hi there")

    assert reply.platform == "slack"
    assert reply.chat_id == "C123"
    assert reply.thread_id == "T456"
    assert reply.text == "hi there"


def test_message_defaults():
    msg = UniversalMessage(platform="telegram", chat_id="1", user_id="2", text="hi")
    assert msg.attachments == []
    assert msg.metadata == {}
    assert msg.id
