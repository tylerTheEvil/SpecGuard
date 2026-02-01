import json
import os
import urllib.error
import urllib.request
from pathlib import Path


def _load_env_if_present() -> None:
    env_path = Path.cwd() / ".env"
    if not env_path.is_file():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(env_path)


class LLMClient:
    def complete(self, system_prompt: str, user_content: str) -> str:
        raise NotImplementedError


class OpenAIClient(LLMClient):
    def __init__(self) -> None:
        from openai import OpenAI

        self._model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        self._client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def complete(self, system_prompt: str, user_content: str) -> str:
        response = self._client.responses.create(
            model=self._model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
        )
        return (
            getattr(response, "output_text", None)
            or (
                response.output[0].content[0].text
                if getattr(response, "output", None)
                else ""
            )
        )


class OllamaClient(LLMClient):
    def __init__(self) -> None:
        self._base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self._model = os.getenv("OLLAMA_MODEL", "llama3.1")

    def complete(self, system_prompt: str, user_content: str) -> str:
        chat_url = f"{self._base_url}/api/chat"
        chat_payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "stream": False,
        }
        chat_data = json.dumps(chat_payload).encode("utf-8")
        chat_request = urllib.request.Request(
            chat_url,
            data=chat_data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(chat_request, timeout=120) as response:
                raw = response.read().decode("utf-8")
            parsed = json.loads(raw)
            content = parsed.get("message", {}).get("content")
            if not content:
                raise RuntimeError(f"Ollama response missing message content: {parsed}")
            return content
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise RuntimeError(f"Failed to reach Ollama at {chat_url}: {exc}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Failed to reach Ollama at {chat_url}: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Invalid JSON from Ollama: {raw}") from exc

        generate_url = f"{self._base_url}/api/generate"
        prompt = f"{system_prompt.strip()}\n\n{user_content.strip()}"
        generate_payload = {"model": self._model, "prompt": prompt, "stream": False}
        generate_data = json.dumps(generate_payload).encode("utf-8")
        generate_request = urllib.request.Request(
            generate_url,
            data=generate_data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(generate_request, timeout=120) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Failed to reach Ollama at {generate_url}: {exc}") from exc

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Invalid JSON from Ollama: {raw}") from exc

        content = parsed.get("response")
        if not content:
            raise RuntimeError(f"Ollama response missing 'response' field: {parsed}")
        return content


def get_llm_client() -> LLMClient:
    _load_env_if_present()
    provider = os.getenv("LLM_PROVIDER")
    if provider is None:
        provider = "openai" if os.getenv("OPENAI_API_KEY") else "ollama"
    provider = provider.lower()

    if provider == "openai":
        return OpenAIClient()
    if provider == "ollama":
        return OllamaClient()

    raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")
