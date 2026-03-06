"""Google Gemini LLM client with retry logic and prompt engineering.

This module provides a wrapper around the Google Gemini API with automatic
retry logic for handling transient failures. It constructs prompts with
system instructions optimized for medical information queries.

Key features:
    - Exponential backoff retry strategy for API resilience
    - Medical-domain prompt engineering with safety constraints
    - Configurable model selection (gemini-2.0-flash, gemini-2.5-pro, etc.)
    - Temperature and token configuration for consistent responses

Example:
    Generate a response with context:
        from src.infra.llm import get_client
        client = get_client()
        response = client.generate(
            prompt="What is a normal cholesterol level?",
            context="Reference information from medical guidelines..."
        )
"""

import logging
import time

import google.genai as genai
from google.genai import types

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
                    delay = INITIAL_DELAY * (2 ** attempt)
                    logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    logger.error(f"All {MAX_RETRIES} attempts failed: {e}")
        if last_exception:
            raise last_exception
        raise RuntimeError("Unexpected error in retry logic")
    return wrapper


class GeminiClient:
    """Google Gemini LLM client with medical-domain prompt engineering.

    Wraps the Google Gemini API with domain-specific prompts for health
    screening interpretation. Includes automatic retry logic and configurable
    model selection.

    Attributes:
        client: Underlying genai.Client instance
        model: Gemini model identifier (e.g., "gemini-2.0-flash")

    Example:
        Create client with default model:
            from src.infra.llm import GeminiClient
            client = GeminiClient()

        Create client with specific model:
            client = GeminiClient(model="gemini-2.5-pro")
    """

    def __init__(self, model: str | None = None):
        """Initialize the Gemini client.

        Args:
            model: Model identifier (e.g., "gemini-2.0-flash", "gemini-2.5-pro")
                   If None, uses the model from settings.model_name
        """
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.model = model or settings.model_name

    @retry_with_backoff
    def generate(self, prompt: str, context: str = "") -> str:
        """Generate a response using Gemini with medical context.

        Constructs a prompt with system instructions for medical information
        assistance and calls the Gemini API. The prompt includes safety rails
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
        full_prompt = f"""You are a helpful medical information assistant.
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
"""

        response = self.client.models.generate_content(
            model=self.model,
            contents=full_prompt,
            config=types.GenerateContentConfig(
                temperature=0.7,
                max_output_tokens=2048,
                system_instruction="You are a medical information assistant that provides educational information about lab tests and health screening results."
            )
        )

        text = response.text
        if text is None:
            raise ValueError("Empty response from Gemini API")
        return text


def get_client() -> GeminiClient:
    """Factory function to create a GeminiClient instance.

    Provides a convenient way to get a client instance without needing to
    import the class directly. Uses default model from settings.

    Returns:
        GeminiClient: Configured client instance

    Example:
        from src.infra.llm import get_client
        client = get_client()
        response = client.generate("Hello")
    """
    return GeminiClient()
