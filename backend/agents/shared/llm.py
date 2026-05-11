"""Groq LLM factory — single cached instance shared across all agent graphs."""
import functools
from langchain_groq import ChatGroq


@functools.lru_cache(maxsize=4)
def get_llm(temperature: float = 0.3) -> ChatGroq:
    """Return a cached ChatGroq instance.

    The GROQ_API_KEY is read from the environment (set in main.py lifespan
    from pydantic-settings before any agent graph runs).
    """
    return ChatGroq(
        model_name="llama-3.3-70b-versatile",
        temperature=temperature,
    )
