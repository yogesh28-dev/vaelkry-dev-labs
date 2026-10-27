"""
Vaelkry Dev Labs - Multi-Agent Enterprise Discord System
Ultra-Fast Groq AI Inference Engine (Llama 3.3 70B & Mixtral)
Provides sub-second dialogue generation and instant voice fallback.
"""

import os
import logging
from typing import Optional, List, Dict
from groq import AsyncGroq

logger = logging.getLogger("VaelkryDevLabs.Groq")

class GroqService:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key:
            logger.warning("GROQ_API_KEY not found in environment. Groq fallback disabled.")
            self.client = None
        else:
            self.client = AsyncGroq(api_key=self.api_key)
            logger.info("Groq Ultra-Fast AI Engine initialized successfully.")

    async def generate_response(
        self,
        system_prompt: str,
        user_message: str,
        model: str = "llama-3.3-70b-versatile",
        temperature: float = 0.7,
        max_tokens: int = 150,
    ) -> Optional[str]:
        """
        Generates rapid micro-dialogue for voice responses and chat interactions.
        """
        if not self.client:
            return None

        try:
            chat_completion = await self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return chat_completion.choices[0].message.content.strip()
        except Exception as exc:
            logger.error(f"Groq generation error: {exc}")
            return None

    async def generate_autonomous_dialogue(
        self,
        character_name: str,
        role: str,
        squad: str,
        context: str,
    ) -> Optional[str]:
        """
        Generates contextual in-character workplace dialogue and banter.
        """
        system_prompt = (
            f"You are {character_name}, working at Vaelkry Dev Labs in {squad} as {role}. "
            "Speak naturally in your signature tone (Tanglish/English mixed if Tamil persona, sharp and charismatic). "
            "Keep responses strictly within 1 to 2 punchy sentences suitable for Discord voice or chat. "
            "Do not output markdown quotes, tags, or narrator intros."
        )
        return await self.generate_response(system_prompt, context)