import logging
from groq import AsyncGroq
from app.core.config import settings

logger = logging.getLogger(__name__)

_client: AsyncGroq = None


def get_groq_client() -> AsyncGroq:
    global _client
    if _client is None:
        _client = AsyncGroq(api_key=settings.GROQ_API_KEY)
        logger.info("Groq client initialized.")
    return _client


async def chat_completion(
    messages: list[dict],
    model: str = None,
    temperature: float = 0.7,
    max_tokens: int = 300,
) -> str:
    """
    Send messages to Groq and return the response text.
    messages format: [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]
    """
    client = get_groq_client()
    model = model or settings.GROQ_MODEL

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        text = response.choices[0].message.content.strip()
        logger.info("Groq response received. Tokens used: %s", response.usage.total_tokens)
        return text

    except Exception as exc:
        logger.exception("Groq API error: %s", exc)
        raise