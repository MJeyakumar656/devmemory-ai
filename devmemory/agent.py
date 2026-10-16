from __future__ import annotations

import os
from typing import Optional

from openai import OpenAI

from .memory import MemoryStore


class DevMemoryAgent:
    """A simple agent that retrieves graph evidence and answers a user question."""

    def __init__(
        self,
        memory_store: Optional[MemoryStore] = None,
        model_name: str = "gpt-4o-mini",
    ):
        self.memory_store = memory_store or MemoryStore(use_local_fallback=True)
        self.model_name = model_name

    def answer(self, question: str) -> str:
        context = self.memory_store.search(question)
        if not context:
            return "I could not find a matching memory for that project or issue. Store a project memory first and ask again."

        evidence = context[0]
        project = evidence["project"]
        issue = evidence["issue"]
        fix = evidence["fix"]
        session = evidence["session"]
        evidence_text = evidence["evidence"]

        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            client = OpenAI(api_key=api_key)
            prompt = (
                "You are a DevMemory AI assistant. Use only the provided evidence. "
                "Answer the user's question using the recorded project memory."
            )
            try:
                response = client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": prompt},
                        {
                            "role": "user",
                            "content": (
                                f"Question: {question}\n\n"
                                f"Evidence: Project={project}; Issue={issue}; Fix={fix}; "
                                f"Session={session}; Notes={evidence_text}"
                            ),
                        },
                    ],
                    temperature=0,
                )
                answer = response.choices[0].message.content
                if answer:
                    return answer
            except Exception:
                pass

        return (
            f"In the {project} project, we fixed the {issue} by {fix}. "
            f"This was recorded in session {session}. Evidence: {evidence_text}."
        )
