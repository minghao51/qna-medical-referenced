import logging
import os
import time

import google.genai as genai
from dotenv import load_dotenv
from google.genai import types

load_dotenv()

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
INITIAL_DELAY = 1.0


def retry_with_backoff(func):
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
    def __init__(self, model: str = "gemini-2.0-flash"):
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.model = model

    @retry_with_backoff
    def generate(self, prompt: str, context: str = "") -> str:
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
    return GeminiClient()
