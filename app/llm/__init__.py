"""LLM package: LangChain assessment chain and safety rules."""

from app.llm.chain import assess, build_chain
from app.llm.safety import CRISIS_MESSAGE_VI, check_crisis

__all__ = ["assess", "build_chain", "check_crisis", "CRISIS_MESSAGE_VI"]
