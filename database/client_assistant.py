"""Authenticated client chat entry point. No message persistence or clinical retrieval."""
from collections import deque
from contextlib import contextmanager
import logging
import os
import threading
import time
from typing import Literal

from fastapi import APIRouter, Header, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator
from ai_harness.client_assistant import generate_reply
from database import client_operations

router = APIRouter(tags=["client assistant"])
LOGGER = logging.getLogger(__name__)
_lock = threading.Lock()
_recent = {}
_active = set()


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=12000)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    messages: list[ChatMessage] = Field(min_length=1, max_length=11)

    @model_validator(mode="after")
    def validate_conversation(self):
        if sum(len(message.content) for message in self.messages) > 16000:
            raise ValueError("Conversation is too long. Start a new chat.")
        for index, message in enumerate(reversed(self.messages)):
            if message.role != ("user" if index % 2 == 0 else "assistant") or not message.content.strip():
                raise ValueError("Submit an alternating conversation ending with a user message.")
            if message.role == "user" and len(message.content) > 2000:
                raise ValueError("Messages must be at most 2000 characters.")
        return self


@contextmanager
def chat_slot(key):
    now = time.monotonic()
    with _lock:
        for old_key in list(_recent):
            if old_key not in _active and (not _recent[old_key] or _recent[old_key][-1] <= now - 600):
                del _recent[old_key]
        recent = _recent.setdefault(key, deque())
        while recent and recent[0] <= now - 600:
            recent.popleft()
        if key in _active or len(_active) >= 8 or len(recent) >= 20 or len(_recent) > 10000:
            raise HTTPException(429, "Please wait before sending another message.", headers={"Retry-After": "60"})
        recent.append(now)
        _active.add(key)
    try:
        yield
    finally:
        with _lock:
            _active.discard(key)


@router.post("/client-assistant/chat")
def chat(payload: ChatRequest, response: Response, authorization: str | None = Header(default=None)):
    response.headers["Cache-Control"] = "no-store"
    def authorize():
        return client_operations.authorized_read(authorization, lambda connection, context: context)
    context = authorize()
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("CLIENT_ASSISTANT_MODEL") or os.getenv("INSIGHTS_MODEL")
    if not api_key or not model:
        raise HTTPException(503, "AI chat is not configured. Please try again later.")
    key = (str(context["organization_id"]), str(context["client_id"]))
    with chat_slot(key):
        try:
            result = generate_reply([message.model_dump() for message in payload.messages],
                api_key=api_key, model=model, authorization=authorization, authorize=authorize)
        except RuntimeError as exc:
            raise HTTPException(502, "The AI response could not be completed. Please try again.") from exc
    LOGGER.info("Client assistant usage model=%s calls=%s input_tokens=%s output_tokens=%s",
                model, result["model_calls"], result["usage"]["input_tokens"], result["usage"]["output_tokens"])
    return {"reply": result["reply"]}
