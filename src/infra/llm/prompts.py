from openai.types.chat import ChatCompletionMessageParam

SYSTEM_PROMPT = "You are a medical information assistant that provides educational information about lab tests and health screening results."

USER_PROMPT_TEMPLATE = """You are a helpful medical information assistant.
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


def build_medical_messages(prompt: str, context: str = "") -> list[ChatCompletionMessageParam]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": USER_PROMPT_TEMPLATE.format(context=context, prompt=prompt)},
    ]
