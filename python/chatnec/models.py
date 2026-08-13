"""Universal message schema shared by every platform adapter and every agent framework."""
from __future__ import annotations

import time
import uuid
from typing import Any, Awaitable, Callable, Optional, Union

from pydantic import BaseModel, Field


class Attachment(BaseModel):
    type: str  # "image" | "file" | "audio" | ...
    url: Optional[str] = None
    name: Optional[str] = None
    content_type: Optional[str] = None


class UniversalMessage(BaseModel):
    """An inbound chat message, normalized from any platform's webhook payload."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    platform: str  # "slack" | "telegram" | "teams"
    chat_id: str  # platform conversation/channel id
    thread_id: Optional[str] = None  # thread/reply-chain id, if the platform has one
    user_id: str
    user_name: Optional[str] = None
    text: str
    attachments: list[Attachment] = Field(default_factory=list)
    timestamp: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = Field(default_factory=dict)
    raw: dict[str, Any] = Field(default_factory=dict)  # original payload, for adapter-specific needs


class UniversalReply(BaseModel):
    """An outbound reply, addressed back to a platform conversation."""

    platform: str
    chat_id: str
    thread_id: Optional[str] = None
    text: str
    attachments: list[Attachment] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def to(cls, message: UniversalMessage, text: str, **kwargs: Any) -> "UniversalReply":
        """Build a reply addressed back to wherever `message` came from."""
        return cls(
            platform=message.platform,
            chat_id=message.chat_id,
            thread_id=message.thread_id,
            text=text,
            **kwargs,
        )


# The one function signature every agent framework needs to implement.
# Return a string, a UniversalReply, or None (no reply sent).
AgentHandler = Callable[
    [UniversalMessage],
    Awaitable[Union[str, UniversalReply, None]],
]
