"""
DOKI GENERATOR — Motor de Linguagem Plugável v1.0
Suporta modelos locais via Ollama (LLaMA, Mistral, Phi, Gemma...)
Fácil de expandir para qualquer modelo open source.
"""
import httpx
import logging
import json
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class DokiGenerator:
    """
    Motor de geração de texto da Doki.
    Por padrão usa Ollama (roda localmente, sem custo, sem API key).
    Configurável via variáveis de ambiente.
    """

    def __init__(self):
        self.backend = settings.LLM_BACKEND           # "ollama" | "openai_compatible"
        self.model = settings.LLM_MODEL               # ex: "mistral", "llama3.2"
        self.base_url = settings.LLM_BASE_URL         # ex: "http://localhost:11434"
        self.api_key = settings.LLM_API_KEY           # opcional (para backends compatíveis)
        self.max_tokens = settings.LLM_MAX_TOKENS
        self.temperature = settings.LLM_TEMPERATURE

    async def generate(
        self,
        system_prompt: str,
        conversation_history: list[dict],
        user_message: str,
    ) -> str:
        """Gera uma resposta usando o backend configurado."""

        if self.backend == "ollama":
            return await self._generate_ollama(system_prompt, conversation_history, user_message)
        elif self.backend == "openai_compatible":
            return await self._generate_openai_compatible(system_prompt, conversation_history, user_message)
        else:
            return await self._fallback_response(user_message)

    async def _generate_ollama(
        self,
        system_prompt: str,
        history: list[dict],
        user_message: str,
    ) -> str:
        """Gera resposta via Ollama (modelos locais)."""

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history[-8:])  # últimas 8 mensagens de contexto
        messages.append({"role": "user", "content": user_message})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                return data["message"]["content"]

        except httpx.ConnectError:
            logger.error("Ollama não está rodando. Inicie com: ollama serve")
            return (
                "⚠️ O motor de linguagem da Doki não está disponível no momento. "
                "Por favor, certifique-se que o Ollama está rodando com `ollama serve` "
                f"e que o modelo `{self.model}` está instalado com `ollama pull {self.model}`."
            )
        except Exception as e:
            logger.error(f"Erro ao gerar resposta (Ollama): {e}")
            return "⚠️ Ocorreu um erro interno. Por favor, tente novamente."

    async def _generate_openai_compatible(
        self,
        system_prompt: str,
        history: list[dict],
        user_message: str,
    ) -> str:
        """
        Gera resposta via API compatível com OpenAI.
        Funciona com: LM Studio, vLLM, Together AI, Groq, etc.
        """

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history[-8:])
        messages.append({"role": "user", "content": user_message})

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.base_url}/v1/chat/completions",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]

        except Exception as e:
            logger.error(f"Erro ao gerar resposta (OpenAI-compatible): {e}")
            return "⚠️ Ocorreu um erro interno. Por favor, tente novamente."

    async def _fallback_response(self, user_message: str) -> str:
        """Resposta de fallback quando nenhum backend está configurado."""
        return (
            "🤖 Olá! Sou a Doki, mas meu motor de linguagem ainda não está configurado. "
            "Configure a variável `LLM_BACKEND` no seu arquivo `.env` para começarmos! "
            "Opções: `ollama` (local, gratuito) ou `openai_compatible`."
        )

    async def health_check(self) -> dict:
        """Verifica se o backend de linguagem está disponível."""
        try:
            if self.backend == "ollama":
                async with httpx.AsyncClient(timeout=5.0) as client:
                    r = await client.get(f"{self.base_url}/api/tags")
                    r.raise_for_status()
                    models = [m["name"] for m in r.json().get("models", [])]
                    return {
                        "status": "ok",
                        "backend": self.backend,
                        "model": self.model,
                        "available_models": models,
                    }
        except Exception as e:
            return {"status": "error", "backend": self.backend, "error": str(e)}

        return {"status": "unknown", "backend": self.backend}


doki_generator = DokiGenerator()
