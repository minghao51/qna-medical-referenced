from typing import Any, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@runtime_checkable
class LLMClient(Protocol):
    def generate(self, prompt: str, context: str = "") -> str: ...

    async def a_generate(self, prompt: str, context: str = "") -> str: ...

    async def a_generate_stream(self, prompt: str, context: str = "") -> Any: ...

    def generate_structured(self, prompt: str, response_model: type[T], context: str = "") -> T: ...

    async def a_generate_structured(
        self, prompt: str, response_model: type[T], context: str = ""
    ) -> T: ...
