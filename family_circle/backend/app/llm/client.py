import os
import json
import re
import logging
import httpx

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_TIMEOUT = 20


async def _call_groq(messages: list[dict]) -> str:
    if not GROQ_API_KEY:
        return "AI недоступен: не указан GROQ_API_KEY."

    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": MODEL,
        "messages": messages,
        "max_tokens": 1024,
        "temperature": 0.7,
    }

    async with httpx.AsyncClient(timeout=GROQ_TIMEOUT) as client:
        response = await client.post(GROQ_API_URL, headers=headers, json=payload)

    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"].strip()


async def chat_dialog(system_prompt: str, user_message: str, history: list[dict] | None = None) -> tuple[str, str | None]:
    messages = [{"role": "system", "content": system_prompt}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    try:
        text = await _call_groq(messages)
    except Exception as e:
        logger.error(f"Groq call failed: {e}")
        return "AI временно недоступен. Пожалуйста, попробуйте ещё раз через несколько минут.", None

    intent_type = None
    json_match = re.search(r'\{("intent_type"\s*:\s*"[^"]+")\}', text, re.DOTALL)
    if json_match:
        try:
            parsed = json.loads("{" + json_match.group(1) + "}")
            intent_type = parsed.get("intent_type")
        except json.JSONDecodeError:
            pass
        text = re.sub(r'\s*\{("intent_type"\s*:\s*"[^"]+")\}\s*$', '', text).strip()

    return text, intent_type


async def generate_synthesis(system_prompt: str) -> str:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Сгенерируй финальный отчёт на основе данных выше."},
    ]
    try:
        return await _call_groq(messages)
    except Exception as e:
        logger.error(f"Groq synthesis failed: {e}")
        return "Не удалось сгенерировать отчёт. Попробуйте позже."
