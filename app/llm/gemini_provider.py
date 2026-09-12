"""Gemini adapter implementing the existing provider contract."""
import asyncio
import json
from typing import Any, Dict, Optional, Type

from pydantic import BaseModel

from app.config import settings
from app.llm.base import LLMProvider
from app.utils.errors import LLMProviderException, MalformedLLMResponseException


class GeminiProvider(LLMProvider):
    def __init__(self):
        if not settings.GEMINI_API_KEY:
            raise LLMProviderException("GEMINI_API_KEY is not configured.")
        try:
            import google.generativeai as genai
        except ImportError as exc:
            raise LLMProviderException("google-generativeai is not installed.") from exc
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel(settings.GEMINI_MODEL)

    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        combined = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        try:
            response = await asyncio.to_thread(self.model.generate_content, combined)
            return response.text or ""
        except Exception as exc:
            raise LLMProviderException(f"Gemini provider error: {exc}") from exc

    async def generate_structured(self, prompt: str, system_prompt: Optional[str] = None,
                                  response_model: Optional[Type[BaseModel]] = None) -> Dict[str, Any]:
        combined = (system_prompt or "") + "\nRespond only with a JSON object.\n\n" + prompt
        try:
            response = await asyncio.to_thread(
                self.model.generate_content, combined,
                generation_config={"response_mime_type": "application/json", "temperature": 0},
            )
            data = json.loads(response.text or "{}")
            return response_model.model_validate(data).model_dump() if response_model else data
        except json.JSONDecodeError as exc:
            raise MalformedLLMResponseException(f"Gemini returned invalid JSON: {exc}") from exc
        except LLMProviderException:
            raise
        except Exception as exc:
            raise LLMProviderException(f"Gemini provider error: {exc}") from exc
