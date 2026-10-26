"""
Vaelkry Dev Labs - Gemini AI Service
Provides asynchronous content generation with fallback models and error resilience.
"""

import logging
from typing import List, Optional
from google import genai
from google.genai import errors

logger = logging.getLogger("VaelkryDevLabs.Gemini")


class GeminiService:
    def __init__(self, api_key: str, candidate_models: Optional[List[str]] = None):
        self.api_key = api_key
        self.client = genai.Client(api_key=api_key)
        self.candidate_models = candidate_models or [
            "gemini-3.5-flash",
            "gemini-flash-lite-latest",
            "gemini-3-flash-preview",
            "gemini-3.8-flash",
        ]

    async def generate_response(self, prompt: str, agent_name: str) -> str:
        """
        Asynchronously generates a response using Gemini, cycling through candidate
        models if any encounters high demand (503) or rate limits.
        """
        last_exception = None

        for model in self.candidate_models:
            try:
                logger.info(f"Generating response for {agent_name} using model: {model}")
                response = await self.client.aio.models.generate_content(
                    model=model,
                    contents=prompt,
                )
                if response and response.text:
                    cleaned_text = response.text.strip()
                    # Safeguard against Discord 2000 char limit
                    if len(cleaned_text) > 1950:
                        cleaned_text = cleaned_text[:1900] + "\n\n*(Content trimmed to fit Discord message limit)*"
                    return cleaned_text
                else:
                    logger.warning(f"Empty response from model {model} for {agent_name}")
            except (errors.APIError, errors.ClientError, Exception) as exc:
                last_exception = exc
                logger.warning(f"Model {model} failed for {agent_name}: {exc}. Trying next fallback...")
                continue

        logger.error(f"All Gemini models exhausted for {agent_name}: {last_exception}")
        # In-character fallback if API experiences transient global outage
        return (
            f"**[{agent_name}]**: Konjam network throttle iruku nanba, "
            f"sprint work-la continue pannuvom! 💻⚡"
        )

    async def generate_casual_chat(
        self,
        prompt: str,
        character_name: str,
    ) -> str:
        """
        Asynchronously generates a punchy, casual Discord player response or roast.
        Cleans up extraneous quotes, bot name prefixes, and ensures maximum 2-line length.
        """
        raw_text = await self.generate_response(prompt=prompt, agent_name=character_name)
        cleaned = raw_text.strip()

        # Remove surrounding quotes if model wrapped output in quotes
        if (cleaned.startswith('"') and cleaned.endswith('"')) or (cleaned.startswith("'") and cleaned.endswith("'")):
            cleaned = cleaned[1:-1].strip()

        import re
        # Strip prefixes like "Vijay: ", "[Vijay]: ", "**Vijay**: "
        cleaned = re.sub(r'^(?:\[.*?\]|\*\*.*?\*\*|[A-Za-z0-9_]+)\s*:\s*', '', cleaned).strip()

        if (cleaned.startswith('"') and cleaned.endswith('"')) or (cleaned.startswith("'") and cleaned.endswith("'")):
            cleaned = cleaned[1:-1].strip()

        lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
        if len(lines) > 2:
            cleaned = " ".join(lines[:2])
        elif lines:
            cleaned = "\n".join(lines)
        else:
            cleaned = "lmao vidu bro paathukalam 💀"

        return cleaned

