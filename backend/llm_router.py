import os
import json
import logging
from typing import List, Dict, Any, Optional, Tuple, AsyncGenerator
import httpx
from groq import Groq
import ollama

from backend.config import (
    OLLAMA_BASE_URL,
    OLLAMA_DEFAULT_MODEL,
    GROQ_API_KEY,
    GROQ_DEFAULT_MODEL,
    GEMINI_API_KEY,
    GEMINI_DEFAULT_MODEL
)
from backend.models import ChatMessage

logger = logging.getLogger("bank_soc.llm_router")
logging.basicConfig(level=logging.INFO)

# Verified supported model fallbacks for Groq
GROQ_CANDIDATE_MODELS = [
    "openai/gpt-oss-120b",
    "qwen/qwen3.8-27b",
    "openai/gpt-oss-20b",
    "qwen/qwen3.6-27b",
    "llama-3.3-70b-versatile"
]

class LLMRouter:
    """
    Intelligent LLM Router supporting Groq Cloud (Free Tier), Ollama (100% Local), and Gemini.
    Features automated health probing, fallback routing, and graceful offline handling.
    """

    def __init__(self):
        self.ollama_base_url = OLLAMA_BASE_URL

    @property
    def groq_api_key(self) -> str:
        return os.getenv("GROQ_API_KEY") or GROQ_API_KEY or ""

    @property
    def gemini_api_key(self) -> str:
        return os.getenv("GEMINI_API_KEY") or GEMINI_API_KEY or ""

    def is_ollama_online(self) -> bool:
        """
        Quick check (under 0.8s) to see if local Ollama daemon is reachable.
        """
        try:
            with httpx.Client(timeout=0.8) as client:
                res = client.get(f"{self.ollama_base_url}/api/version")
                return res.status_code == 200
        except Exception:
            return False

    def get_effective_provider(self, requested_provider: Optional[str] = "auto", custom_key: Optional[str] = None) -> Tuple[str, str, Optional[str]]:
        """
        Determines the provider and model to use based on user preference, key availability, and local daemon status.
        """
        active_groq_key = custom_key if (custom_key and custom_key.startswith("gsk_")) else self.groq_api_key
        active_gemini_key = custom_key if (custom_key and custom_key.startswith("AIza")) else self.gemini_api_key

        req = (requested_provider or "auto").lower()
        ollama_alive = self.is_ollama_online()

        # Explicit Groq request
        if req == "groq":
            if active_groq_key:
                return "groq", os.getenv("GROQ_DEFAULT_MODEL", GROQ_DEFAULT_MODEL), active_groq_key
            elif active_gemini_key:
                logger.warning("Groq requested without key, falling back to Gemini.")
                return "gemini", os.getenv("GEMINI_DEFAULT_MODEL", GEMINI_DEFAULT_MODEL), active_gemini_key
            elif ollama_alive:
                logger.warning("Groq requested without key, falling back to local Ollama.")
                return "ollama", os.getenv("OLLAMA_DEFAULT_MODEL", OLLAMA_DEFAULT_MODEL), None
            else:
                return "groq", os.getenv("GROQ_DEFAULT_MODEL", GROQ_DEFAULT_MODEL), ""

        # Explicit Gemini request
        if req == "gemini":
            if active_gemini_key:
                return "gemini", os.getenv("GEMINI_DEFAULT_MODEL", GEMINI_DEFAULT_MODEL), active_gemini_key
            elif active_groq_key:
                logger.warning("Gemini requested without key, falling back to Groq.")
                return "groq", os.getenv("GROQ_DEFAULT_MODEL", GROQ_DEFAULT_MODEL), active_groq_key
            elif ollama_alive:
                return "ollama", os.getenv("OLLAMA_DEFAULT_MODEL", OLLAMA_DEFAULT_MODEL), None
            else:
                return "gemini", os.getenv("GEMINI_DEFAULT_MODEL", GEMINI_DEFAULT_MODEL), ""

        # Explicit Ollama request
        if req == "ollama":
            if ollama_alive:
                return "ollama", os.getenv("OLLAMA_DEFAULT_MODEL", OLLAMA_DEFAULT_MODEL), None
            # If user quit/stopped Ollama, smart fallback to Groq or Gemini if keys exist
            if active_groq_key:
                logger.info("Ollama is offline. Automatically routing to active Groq Cloud.")
                return "groq", os.getenv("GROQ_DEFAULT_MODEL", GROQ_DEFAULT_MODEL), active_groq_key
            elif active_gemini_key:
                logger.info("Ollama is offline. Automatically routing to Google Gemini.")
                return "gemini", os.getenv("GEMINI_DEFAULT_MODEL", GEMINI_DEFAULT_MODEL), active_gemini_key
            else:
                return "ollama", os.getenv("OLLAMA_DEFAULT_MODEL", OLLAMA_DEFAULT_MODEL), None

        # Auto Mode Priority: Groq -> Gemini -> Ollama
        if active_groq_key:
            return "groq", os.getenv("GROQ_DEFAULT_MODEL", GROQ_DEFAULT_MODEL), active_groq_key
        elif active_gemini_key:
            return "gemini", os.getenv("GEMINI_DEFAULT_MODEL", GEMINI_DEFAULT_MODEL), active_gemini_key
        elif ollama_alive:
            return "ollama", os.getenv("OLLAMA_DEFAULT_MODEL", OLLAMA_DEFAULT_MODEL), None
        else:
            # Fallback placeholder
            return "ollama", os.getenv("OLLAMA_DEFAULT_MODEL", OLLAMA_DEFAULT_MODEL), None

    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        provider: Optional[str] = "auto",
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: float = 0.0
    ) -> Dict[str, Any]:
        """
        Generate completion using selected or auto-routed provider with automatic model fallbacks.
        """
        active_provider, default_model, key = self.get_effective_provider(provider, api_key)
        active_model = model_name or default_model

        if active_provider == "groq":
            if not key:
                raise RuntimeError("Groq API Key is not configured. Please add GROQ_API_KEY in .env or Settings modal.")
            return await self._call_groq(messages, active_model, key, temperature)

        elif active_provider == "gemini":
            if not key:
                raise RuntimeError("Gemini API Key is not configured. Please add GEMINI_API_KEY in .env or Settings modal.")
            return await self._call_gemini(messages, active_model, key, temperature)

        else:
            if not self.is_ollama_online():
                raise RuntimeError(
                    f"Ollama local daemon is not running on {self.ollama_base_url}. "
                    "Start Ollama with 'ollama serve' or switch to Groq Cloud in Settings (⚙️)."
                )
            return await self._call_ollama(messages, active_model, temperature)

    async def stream_response(
        self,
        messages: List[Dict[str, str]],
        provider: Optional[str] = "auto",
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: float = 0.0
    ) -> AsyncGenerator[str, None]:
        """
        Stream tokens directly to client via async generator with fallback resilience.
        """
        active_provider, default_model, key = self.get_effective_provider(provider, api_key)
        active_model = model_name or default_model

        if active_provider == "groq":
            if not key:
                raise RuntimeError("Groq API Key is not configured. Please add GROQ_API_KEY in .env or Settings modal.")
            
            client = Groq(api_key=key)
            models_to_try = [active_model] + [m for m in GROQ_CANDIDATE_MODELS if m != active_model]
            
            stream = None
            for candidate in models_to_try:
                try:
                    stream = client.chat.completions.create(
                        model=candidate,
                        messages=messages,
                        temperature=temperature,
                        stream=True
                    )
                    break
                except Exception as e:
                    logger.warning(f"Groq stream failed with model {candidate}: {e}")
                    if candidate == models_to_try[-1]:
                        raise

            if stream:
                for chunk in stream:
                    content = chunk.choices[0].delta.content or ""
                    if content:
                        yield content

        elif active_provider == "gemini":
            if not key:
                raise RuntimeError("Gemini API Key is not configured. Please add GEMINI_API_KEY in .env or Settings modal.")

            url = f"https://generativelanguage.googleapis.com/v1beta/models/{active_model}:streamGenerateContent?key={key}"
            payload = {
                "contents": [
                    {"role": "user" if m["role"] in ["user", "system"] else "model", "parts": [{"text": m["content"]}]}
                    for m in messages
                ],
                "generationConfig": {"temperature": temperature}
            }
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream("POST", url, json=payload) as response:
                    if response.status_code != 200:
                        err_text = await response.aread()
                        raise RuntimeError(f"Gemini API error ({response.status_code}): {err_text.decode('utf-8', errors='replace')}")
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data_str = line[6:].strip()
                            if not data_str:
                                continue
                            try:
                                data_json = json.loads(data_str)
                                candidates = data_json.get("candidates", [])
                                if candidates and "content" in candidates[0]:
                                    parts = candidates[0]["content"].get("parts", [])
                                    for p in parts:
                                        if "text" in p and p["text"]:
                                            yield p["text"]
                            except Exception:
                                pass

        else:
            if not self.is_ollama_online():
                raise RuntimeError(
                    f"Ollama local daemon is not running on {self.ollama_base_url}. "
                    "Start Ollama with 'ollama serve' or switch to Groq Cloud in Settings (⚙️)."
                )

            client = ollama.Client(host=self.ollama_base_url)
            stream = client.chat(
                model=active_model,
                messages=messages,
                options={"temperature": temperature},
                stream=True
            )
            for chunk in stream:
                content = chunk.get("message", {}).get("content", "")
                if content:
                    yield content

    async def _call_groq(self, messages: List[Dict[str, str]], model: str, api_key: str, temperature: float) -> Dict[str, Any]:
        client = Groq(api_key=api_key)
        models_to_try = [model] + [m for m in GROQ_CANDIDATE_MODELS if m != model]
        
        last_error = None
        for candidate in models_to_try:
            try:
                completion = client.chat.completions.create(
                    model=candidate,
                    messages=messages,
                    temperature=temperature
                )
                return {
                    "content": completion.choices[0].message.content,
                    "provider": "groq",
                    "model": candidate
                }
            except Exception as e:
                logger.warning(f"Groq call failed with model {candidate}: {e}")
                last_error = e
        
        raise last_error or RuntimeError("All Groq model candidates failed.")

    async def _call_ollama(self, messages: List[Dict[str, str]], model: str, temperature: float, max_tokens: int = 800) -> Dict[str, Any]:
        client = ollama.Client(host=self.ollama_base_url)
        response = client.chat(
            model=model,
            messages=messages,
            options={"temperature": temperature, "num_predict": max_tokens}
        )
        return {
            "content": response["message"]["content"],
            "provider": "ollama",
            "model": model
        }

    async def _call_gemini(self, messages: List[Dict[str, str]], model: str, api_key: str, temperature: float) -> Dict[str, Any]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        formatted_contents = []
        for m in messages:
            role = "user" if m["role"] in ["user", "system"] else "model"
            formatted_contents.append({"role": role, "parts": [{"text": m["content"]}]})

        payload = {
            "contents": formatted_contents,
            "generationConfig": {"temperature": temperature}
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                raise RuntimeError(f"Gemini API error ({resp.status_code}): {resp.text}")
            data = resp.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            return {
                "content": text,
                "provider": "gemini",
                "model": model
            }

    def check_health(self) -> Dict[str, Any]:
        """
        Check live health and connectivity of LLM providers.
        """
        ollama_ok = False
        ollama_models = []
        try:
            if self.is_ollama_online():
                client = ollama.Client(host=self.ollama_base_url)
                models_res = client.list()
                ollama_ok = True
                ollama_models = [m.model for m in models_res.models] if hasattr(models_res, "models") else [m.get("name") for m in models_res.get("models", [])]
        except Exception as e:
            logger.debug(f"Ollama health check error: {e}")

        active_provider, active_model, _ = self.get_effective_provider("auto")

        return {
            "ollama_online": ollama_ok,
            "ollama_models": ollama_models,
            "groq_configured": bool(self.groq_api_key),
            "gemini_configured": bool(self.gemini_api_key),
            "active_default_provider": active_provider,
            "active_default_model": active_model
        }

Tuple_Provider = tuple[str, str, Optional[str]]
