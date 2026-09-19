import json
import logging
import re
from typing import List, Dict, Any, Optional
import httpx
from core import config

logger = logging.getLogger("ModelRouter")

EFFORT_MAP = {"low": "low", "normal": "medium", "long": "high"}
MAXTOKENS_MAP = {"low": 512, "normal": 1000, "long": 1400}


class ModelRouter:
    def __init__(self):
        self.openrouter_key = config.OPENROUTER_API_KEY
        self.local_endpoint = config.LOCAL_ENDPOINT
        self.http_client = httpx.AsyncClient(timeout=120.0)

    def get_model_for_role(self, role: str, complexity: str = "normal", requires_vision: bool = False) -> str:
        """Route model based on role, complexity, and vision requirement."""
        if requires_vision:
            return config.EXPERT_MODEL
        if role in ("main_brain", "pm", "qa_auditor") or complexity == "complex":
            return config.EXPERT_MODEL
        if role in ("coder", "data_analyst"):
            return config.WORKER_MODEL
        return config.INSTANT_MODEL

    async def call_openrouter(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        system: Optional[str] = None,
        deepthink: str = "normal",
        max_tokens: Optional[int] = None,
        json_mode: bool = False,
    ) -> str:
        if not self.openrouter_key:
            raise ValueError("No OPENROUTER_API_KEY found in .env file.")

        model_name = model or config.INSTANT_MODEL
        full_messages = []
        if system:
            full_messages.append({"role": "system", "content": system})
        full_messages.extend(messages)

        body: Dict[str, Any] = {
            "model": model_name,
            "messages": full_messages,
            "max_tokens": max_tokens or MAXTOKENS_MAP.get(deepthink, 2048),
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}

        # Add reasoning effort if model supports it
        supports_reasoning = any(m in model_name for m in ["claude", "o1", "o3", "r1", "deepseek"])
        if supports_reasoning and deepthink in EFFORT_MAP:
            body["reasoning"] = {"effort": EFFORT_MAP[deepthink]}

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.openrouter_key}",
            "HTTP-Referer": config.APP_URL,
            "X-Title": config.APP_NAME,
        }

        try:
            resp = await self.http_client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=body,
            )
            if resp.status_code == 400 and "reasoning" in body:
                body.pop("reasoning", None)
                resp = await self.http_client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=body,
                )

            # Adaptive handling for OpenRouter 402 (low credits or max_tokens too high)
            if resp.status_code == 402:
                msg = resp.text
                logger.warning(f"OpenRouter 402 Credit Alert: {msg}")
                match = re.search(r"can only afford (\d+)", msg)
                if match:
                    afforded = int(match.group(1))
                    reduced = max(200, min(500, afforded - 50))
                    logger.info(f"Retrying OpenRouter with clamped max_tokens={reduced}")
                    body["max_tokens"] = reduced
                    resp = await self.http_client.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers=headers,
                        json=body,
                    )

                # Fallback to ultra-low cost model (openai/gpt-4o-mini is ~100x cheaper than claude)
                if resp.status_code in (402, 404) and body.get("model") != "openai/gpt-4o-mini":
                    logger.info("Falling back to ultra-low-cost model: openai/gpt-4o-mini")
                    body["model"] = "openai/gpt-4o-mini"
                    body.pop("reasoning", None)
                    body["max_tokens"] = min(body.get("max_tokens", 800), 800)
                    resp = await self.http_client.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers=headers,
                        json=body,
                    )

            resp.raise_for_status()
            data = resp.json()
            choice = data["choices"][0]
            content = choice["message"].get("content", "")
            return content.strip() if content else ""
        except httpx.HTTPStatusError as e:
            msg = e.response.text
            logger.error(f"OpenRouter HTTP error {e.response.status_code}: {msg}")
            raise RuntimeError(f"OpenRouter API error ({e.response.status_code}): {msg}")
        except Exception as e:
            logger.error(f"OpenRouter call failed: {e}")
            raise

    async def call_structured(
        self,
        messages: List[Dict[str, Any]],
        system: Optional[str] = None,
        model: Optional[str] = None,
        deepthink: str = "normal",
    ) -> Dict[str, Any]:
        """Calls model and guarantees extracted JSON object."""
        system_prompt = (system or "") + "\n\nCRITICAL: Return strictly a valid JSON object. Do not include markdown code block quotes (like ```json), commentary, or extra text outside the JSON object."
        raw = await self.call_openrouter(
            messages=messages,
            system=system_prompt,
            model=model,
            deepthink=deepthink,
            json_mode=True,
        )
        return self.extract_json(raw)

    @staticmethod
    def extract_json(text: str) -> Dict[str, Any]:
        """Robustly extracts JSON object from model output."""
        cleaned = re.sub(r"^```(?:json)?", "", text.strip(), flags=re.MULTILINE)
        cleaned = re.sub(r"```$", "", cleaned.strip(), flags=re.MULTILINE).strip()
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            json_str = cleaned[start : end + 1]
            try:
                return json.loads(json_str)
            except json.JSONDecodeError as e:
                logger.warning(f"Failed parsing slice, attempting fuzzy replace: {e}")
        try:
            return json.loads(cleaned)
        except Exception as e:
            raise ValueError(f"Could not parse valid JSON from LLM response: {cleaned[:200]}... Error: {e}")


model_router = ModelRouter()
