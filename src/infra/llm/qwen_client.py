"""Alibaba Qwen LLM client with retry logic and prompt engineering.

This module provides a wrapper around the Qwen API (via Dashscope's OpenAI-compatible
endpoint) with automatic retry logic for handling transient failures. It constructs
prompts with system instructions optimized for medical information queries.

Key features:
    - Exponential backoff retry strategy for API resilience
    - Medical-domain prompt engineering with safety constraints
    - Configurable model selection (qwen3.5-flash, qwen3.5-plus, qwen-plus, etc.)
    - Temperature and token configuration for consistent responses

Example:
    Generate a response with context:
        from src.infra.llm.qwen_client import get_client
        client = get_client()
        response = client.generate(
            prompt="What is a normal cholesterol level?",
            context="Reference information from medical guidelines..."
        )
"""

import logging
import time

from openai import OpenAI

from src.config import settings

logger = logging.getLogger(__name__)

# Retry configuration
# Maximum attempts before giving up
MAX_RETRIES = 3
# Initial delay in seconds (doubles each retry: 1s, 2s, 4s)
INITIAL_DELAY = 1.0


def retry_with_backoff(func):
    """Decorator that adds exponential backoff retry logic to a function.

    Retries the wrapped function up to MAX_RETRIES times with exponentially
    increasing delays between attempts. Logs warnings for retries and errors
    for final failures.

    Args:
        func: The function to wrap with retry logic

    Returns:
        The wrapped function with retry capability

    Raises:
        Exception: The last exception encountered if all retries fail

    Example:
        @retry_with_backoff
        def unstable_api_call():
            # Might fail transiently
            return requests.get("https://api.example.com")
    """

    def wrapper(*args, **kwargs):
        last_exception: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < MAX_RETRIES - 1:
                    delay = INITIAL_DELAY * (2**attempt)
                    logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    logger.error(f"All {MAX_RETRIES} attempts failed: {e}")
        if last_exception:
            raise last_exception
        raise RuntimeError("Unexpected error in retry logic")

    return wrapper


class QwenClient:
    """Alibaba Qwen LLM client with medical-domain prompt engineering.

    Wraps the Qwen API (via Dashscope's OpenAI-compatible endpoint) with
    domain-specific prompts for health screening interpretation. Includes
    automatic retry logic and configurable model selection.

    Attributes:
        client: Underlying OpenAI client instance (pointing to Dashscope)
        model: Qwen model identifier (e.g., "qwen3.5-flash")

    Example:
        Create client with default model:
            from src.infra.llm.qwen_client import QwenClient
            client = QwenClient()

        Create client with specific model:
            client = QwenClient(model="qwen-plus")
    """

    def __init__(self, model: str | None = None):
        """Initialize the Qwen client.

        Args:
            model: Model identifier (e.g., "qwen3.5-flash", "qwen3.5-plus")
                   If None, uses the model from settings.model_name
        """
        self.client = OpenAI(api_key=settings.dashscope_api_key, base_url=settings.qwen_base_url)
        self.model = model or settings.model_name

    @retry_with_backoff
    def generate(self, prompt: str, context: str = "") -> str:
        """Generate a response using Qwen with medical context.

        Constructs a prompt with system instructions for medical information
        assistance and calls the Qwen API. The prompt includes safety rails
        to prevent medical diagnosis and encourage consulting healthcare providers.

        Args:
            prompt: User's question or query
            context: Retrieved reference information to base the answer on

        Returns:
            Generated response text from the model

        Raises:
            ValueError: If the API returns an empty response
            Exception: If all retry attempts fail (varies by error type)

        Prompt template:
            The full prompt combines:
            - System instructions for medical information assistant role
            - Reference context (from RAG retrieval)
            - User question
            - Safety instructions (no diagnosis, consult provider)
        """
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a medical information assistant that provides educational information about lab tests and health screening results.",
                },
                {
                    "role": "user",
                    "content": f"""You are a helpful medical information assistant.
Based on the following reference information, answer the user's question.

Reference Information:
{context}

User Question: {prompt}

Instructions:
- Provide evidence-based information
- Always recommend consulting with a healthcare provider
- Include relevant reference ranges when applicable
- Mention potential controversies or limitations of tests
- Do not provide medical diagnoses
""",
                },
            ],
            temperature=0.7,
            max_tokens=2048,
        )

        content = response.choices[0].message.content
        if content is None:
            raise ValueError("Empty response from Qwen API")
        return content


def get_client() -> QwenClient:
    """Factory function to create a QwenClient instance.

    Provides a convenient way to get a client instance without needing to
    import the class directly. Uses default model from settings.

    Returns:
        QwenClient: Configured client instance

    Example:
        from src.infra.llm.qwen_client import get_client
        client = get_client()
        response = client.generate("Hello")
    """
    return QwenClient()
