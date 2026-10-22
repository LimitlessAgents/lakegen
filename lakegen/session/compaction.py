from lakegen.prompt import COMPACTION_PROMPT
from lakegen.inference import Router
from lakegen.inference.model import ChatRequest, Message, Role
from lakegen.agent import Conversation

import threading
 

def compact(
    inference_router: Router,
    provider: str,
    model: str,
    conversation: Conversation,
    cancel_event: threading.Event,
    base_url: str | None = None,
) -> Message:
    compact_instruction="Now write the compacted summary of the conversation above."
    request = ChatRequest(
        model=model,
        system_prompt=COMPACTION_PROMPT,
        messages=[
            *conversation.messages,
            Message(role=Role.USER,content=compact_instruction)
        ],
        tools=[],
        base_url=base_url,
    )
        
    # stream() wires into OpenAI's waiter thread and
    ## aborts the socket immediately on cancel_event
    text_parts: list[str] = []
    for chunk in inference_router.stream(provider, request, cancel_event=cancel_event):
        if cancel_event.is_set():
            return Message(role=Role.USER, content="")
        if chunk.text:
            text_parts.append(chunk.text)
    if cancel_event.is_set():
        return Message(role=Role.USER, content="")
    return Message(role=Role.USER, content="".join(text_parts))
