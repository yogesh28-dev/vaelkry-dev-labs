"""
Vaelkry Dev Labs - Casual Discord Player & Roasting Service
Coordinates realistic, casual Discord player interactions, witty comebacks,
playful roasts, and multi-bot banter between:
- Team Vasan (TTF Vasan, Pradeep, Mamitha, Kayadu, Muthazhagi)
- Team Vijay (Vijay, Sivakarthikeyan, Anirudh, Trisha, Lokesh)
- Executive Suite (SadieSink, MillieBobbyBrown)
"""

import asyncio
import logging
import random
import re
from typing import Any, Dict, List, Optional

import discord

from agents import (
    CASUAL_PLAYER_CHARACTERS,
    EXECUTIVE_BOT_KEYS,
    TEAM_VASAN_KEYS,
    TEAM_VIJAY_KEYS,
    build_banter_exchange_prompt,
    build_casual_player_prompt,
    build_cross_team_clash_prompt,
)

logger = logging.getLogger("VaelkryDevLabs.CasualPlayer")


def is_common_channel(channel: discord.abc.Messageable) -> bool:
    """Checks if channel is a community hangout or dev workspace channel."""
    name = getattr(channel, "name", "").lower()
    return any(k in name for k in ("team-chat", "working-chat", "lounge", "cafeteria", "hangout", "the-launchpad", "yogesh-chat"))


class CasualPlayerService:
    def __init__(self, orchestrator: Any):
        self.orchestrator = orchestrator
        self._webhook_cache: Dict[int, discord.Webhook] = {}
        self._chat_history: Dict[int, List[dict]] = {}
        self._banter_lock = asyncio.Lock()

    def _record_message(self, channel_id: int, sender: str, text: str):
        if channel_id not in self._chat_history:
            self._chat_history[channel_id] = []
        self._chat_history[channel_id].append({"sender": sender, "text": text})
        if len(self._chat_history[channel_id]) > 14:
            self._chat_history[channel_id] = self._chat_history[channel_id][-14:]

    def get_recent_context(self, channel_id: int) -> List[dict]:
        return self._chat_history.get(channel_id, [])[-4:]

    async def get_or_create_webhook(self, channel: discord.TextChannel) -> Optional[discord.Webhook]:
        """
        Retrieves or provisions a webhook in the specified text channel so that
        guest community players (Vijay, Sivakarthikeyan, Anirudh, Trisha, Lokesh)
        can post with their personalized avatar and name.
        """
        if channel.id in self._webhook_cache:
            wh = self._webhook_cache[channel.id]
            if getattr(wh, "channel_id", None) == channel.id:
                return wh

        try:
            webhooks = await channel.webhooks()
            for wh in webhooks:
                if wh.name in ("VaelkryPlayerRelay", "VaelkryCafeteria", "VaelkryRelay"):
                    self._webhook_cache[channel.id] = wh
                    return wh

            wh = await channel.create_webhook(name="VaelkryPlayerRelay")
            self._webhook_cache[channel.id] = wh
            return wh
        except (discord.Forbidden, discord.HTTPException, Exception) as exc:
            logger.debug(f"Webhook unavailable in channel {channel.name}: {exc}")
            return None

    async def send_character_chat(
        self,
        channel: discord.abc.Messageable,
        character_key: str,
        text: str,
    ):
        """
        Dispatches a casual chat message:
        - If character_key corresponds to an active bot client (Team Vasan, Sadie, Millie),
          that bot's native Discord client sends the message directly.
        - If character_key is a VIP guest (Vijay, SK, Anirudh, Trisha, Lokesh),
          it routes through a channel Webhook with full avatar/name identity,
          falling back to a styled character badge.
        """
        char_key = character_key.lower().strip()
        char_info = CASUAL_PLAYER_CHARACTERS.get(char_key, CASUAL_PLAYER_CHARACTERS["vijay"])

        # Check if character has an active discord.Client session
        if char_key in self.orchestrator.clients:
            client = self.orchestrator.clients[char_key]
            target_ch = client.get_channel(channel.id) if hasattr(channel, "id") else channel
            if target_ch:
                await target_ch.send(text)
                if hasattr(channel, "id"):
                    self._record_message(channel.id, char_info["name"], text)
                return

        # Guest VIP Player: Attempt webhook delivery
        if isinstance(channel, discord.TextChannel):
            wh = await self.get_or_create_webhook(channel)
            if wh:
                try:
                    await wh.send(
                        content=text,
                        username=char_info["name"],
                        avatar_url=char_info.get("avatar"),
                    )
                    self._record_message(channel.id, char_info["name"], text)
                    return
                except Exception as exc:
                    logger.debug(f"Webhook dispatch failed: {exc}, using fallback client.")

        # Fallback: Send through TTF Vasan or available client with clean character badge
        fallback_client = self.orchestrator.clients.get("ttf_vasan") or next(
            iter(self.orchestrator.clients.values()), None
        )
        if fallback_client:
            target_ch = (
                fallback_client.get_channel(channel.id)
                if hasattr(channel, "id")
                else channel
            )
            if target_ch:
                await target_ch.send(f"**[{char_info['title']}]**: {text}")
                if hasattr(channel, "id"):
                    self._record_message(channel.id, char_info["name"], text)

    async def trigger_bot_comeback(
        self,
        channel: discord.abc.Messageable,
        previous_char_key: str,
        previous_text: str,
    ):
        """
        Spawns an instant, natural, witty comeback or playful counter from a rival
        or teammate bot in common channels (#team-chat, #working-chat, #lounge).
        """
        char_info = CASUAL_PLAYER_CHARACTERS.get(previous_char_key, {})
        rivals = char_info.get("rival_keys", [])
        if not rivals:
            rivals = TEAM_VIJAY_KEYS if char_info.get("team") == "team_vasan" else TEAM_VASAN_KEYS

        comeback_key = random.choice(rivals)
        comeback_info = CASUAL_PLAYER_CHARACTERS.get(comeback_key, CASUAL_PLAYER_CHARACTERS["sivakarthikeyan"])
        ch_name = getattr(channel, "name", "channel")

        prompt = build_casual_player_prompt(
            character_key=comeback_key,
            message=previous_text,
            is_bot_reply=True,
            reply_to_bot=char_info.get("name", previous_char_key),
            channel_name=ch_name,
        )

        try:
            await asyncio.sleep(random.uniform(1.2, 2.2))
            reply = await self.orchestrator.gemini_service.generate_casual_chat(
                prompt=prompt,
                character_name=comeback_info["name"],
            )
            await self.send_character_chat(channel, comeback_key, reply)
        except Exception as exc:
            logger.debug(f"Comeback error for {comeback_key}: {exc}")

    async def chat(
        self,
        character_key: str,
        message: str,
        sender_name: str,
        channel: discord.abc.Messageable,
        allow_comeback: bool = True,
    ) -> str:
        """
        Generates and delivers a single, authentic, casual Discord player reaction,
        with optional spontaneous bot comeback in common channels.
        """
        char_key = character_key.lower().strip()
        char_info = CASUAL_PLAYER_CHARACTERS.get(char_key, CASUAL_PLAYER_CHARACTERS["vijay"])

        ch_id = getattr(channel, "id", 0)
        ch_name = getattr(channel, "name", "channel")
        recent_ctx = self.get_recent_context(ch_id)
        self._record_message(ch_id, sender_name, message)

        prompt = build_casual_player_prompt(
            character_key=char_key,
            message=message,
            sender_name=sender_name,
            recent_context=recent_ctx,
            is_roast=False,
            channel_name=ch_name,
        )

        try:
            reply = await self.orchestrator.gemini_service.generate_casual_chat(
                prompt=prompt,
                character_name=char_info["name"],
            )
            await self.send_character_chat(channel, char_key, reply)

            # Trigger spontaneous comeback in common channels 50% of the time
            if allow_comeback and is_common_channel(channel) and random.random() < 0.55:
                asyncio.create_task(
                    self.trigger_bot_comeback(
                        channel=channel,
                        previous_char_key=char_key,
                        previous_text=reply,
                    )
                )
            return reply
        except Exception as exc:
            logger.exception(f"Error in casual chat for {char_key}: {exc}")
            fallback = char_info.get("sample", "macha paathukalam vidu")
            await self.send_character_chat(channel, char_key, fallback)
            return fallback

    async def roast(
        self,
        character_key: str,
        target: str,
        topic: str,
        sender_name: str,
        channel: discord.abc.Messageable,
        allow_comeback: bool = True,
    ) -> str:
        """
        Delivers a savage, witty Tanglish roast or counter from the specified character,
        with spontaneous teammate laughter or rival comeback.
        """
        char_key = character_key.lower().strip()
        char_info = CASUAL_PLAYER_CHARACTERS.get(char_key, CASUAL_PLAYER_CHARACTERS["sivakarthikeyan"])

        ch_id = getattr(channel, "id", 0)
        ch_name = getattr(channel, "name", "channel")
        recent_ctx = self.get_recent_context(ch_id)

        prompt = build_casual_player_prompt(
            character_key=char_key,
            message=topic or "overall coding logic and scene podradhu",
            sender_name=sender_name,
            recent_context=recent_ctx,
            is_roast=True,
            roast_target=target,
            channel_name=ch_name,
        )

        try:
            roast_line = await self.orchestrator.gemini_service.generate_casual_chat(
                prompt=prompt,
                character_name=char_info["name"],
            )
            await self.send_character_chat(channel, char_key, roast_line)

            # Trigger a witty comeback or laughing reaction from a teammate or rival
            if allow_comeback and is_common_channel(channel):
                asyncio.create_task(
                    self.trigger_bot_comeback(
                        channel=channel,
                        previous_char_key=char_key,
                        previous_text=f"roast against {target}: {roast_line}",
                    )
                )
            return roast_line
        except Exception as exc:
            logger.exception(f"Error in roast for {char_key}: {exc}")
            fallback = f"dei {target}, scene podatha da mudila bro 😂"
            await self.send_character_chat(channel, char_key, fallback)
            return fallback

    async def banter(
        self,
        topic: str,
        channel: discord.abc.Messageable,
    ):
        """
        Executes a rapid-fire 4-line mini roast battle / banter among community players.
        """
        if self._banter_lock.locked():
            await channel.send("🔥 **Hold on macha!** Oru banter already chat-la fire aagittu iruku!")
            return

        async with self._banter_lock:
            prompt = build_banter_exchange_prompt(topic=topic)
            try:
                raw_text = await self.orchestrator.gemini_service.generate_response(
                    prompt=prompt,
                    agent_name="CommunityBanter",
                )

                parsed_turns: List[tuple[str, str]] = []
                for line in raw_text.splitlines():
                    match = re.match(r"^\[([a-zA-Z0-9_]+)\]:\s*(.+)$", line.strip())
                    if match:
                        k = match.group(1).lower().strip()
                        msg = match.group(2).strip()
                        if k in CASUAL_PLAYER_CHARACTERS:
                            parsed_turns.append((k, msg))

                if not parsed_turns:
                    parsed_turns = [
                        ("sivakarthikeyan", f"dei un {topic} ah paatha server ke kannu verkum da 😂"),
                        ("ttf_vasan", "nanba time waste panna koodadhu, 299 speed-la solve panrom!"),
                        ("pradeep", "thalaiva wait panni paaru, logic puriyama kathatha bro 💀"),
                        ("trisha", "ok boys whatever u say 💅"),
                        ("lokesh", "pesunathu podhum, deploy pannitu pesunga."),
                    ]

                for char_key, msg in parsed_turns[:5]:
                    await asyncio.sleep(random.uniform(1.2, 2.0))
                    await self.send_character_chat(channel, char_key, msg)

            except Exception as exc:
                logger.exception(f"Error running banter exchange: {exc}")
                await channel.send("💀 Banter server konjam lag aachu nanba, paathukalam vidu!")

    async def clash(
        self,
        topic: str,
        channel: discord.abc.Messageable,
    ):
        """
        Executes a full-scale Team Vasan vs Team Vijay witty roast battle.
        """
        if self._banter_lock.locked():
            await channel.send("⚔️ **Wait panni paaru machan!** Oru squad clash already live-la iruku! 🔥")
            return

        async with self._banter_lock:
            prompt = build_cross_team_clash_prompt(topic=topic)
            try:
                raw_text = await self.orchestrator.gemini_service.generate_response(
                    prompt=prompt,
                    agent_name="SquadClash",
                )
                parsed_turns: List[tuple[str, str]] = []
                for line in raw_text.splitlines():
                    match = re.match(r"^\[([a-zA-Z0-9_]+)\]:\s*(.+)$", line.strip())
                    if match:
                        k = match.group(1).lower().strip()
                        msg = match.group(2).strip()
                        if k in CASUAL_PLAYER_CHARACTERS:
                            parsed_turns.append((k, msg))

                if not parsed_turns:
                    parsed_turns = [
                        ("ttf_vasan", f"nanba 299 speed-la {topic} solve panrom, Team Vasan mass da!"),
                        ("sivakarthikeyan", "dei throttle twist panra speed-la code crash aagi client kannu verkum da 😂"),
                        ("pradeep", "thalaiva wait panni paaru, logic puriyama comedy pannatha bro 💀"),
                        ("vijay", "cool machan, timing super aana deploy mudinjutha illa thirumba bug ah?"),
                        ("anirudh", "bgm podhum da, sprint marathon 3am beat drop aagudhu! 🎵"),
                        ("trisha", "ok boys keep dreaming, whatever u say 💅"),
                        ("lokesh", "pesunathu podhum da, deploy pannitu pesunga."),
                    ]

                for char_key, msg in parsed_turns[:7]:
                    await asyncio.sleep(random.uniform(1.3, 2.2))
                    await self.send_character_chat(channel, char_key, msg)

            except Exception as exc:
                logger.exception(f"Error during squad clash: {exc}")
                await channel.send("💀 Squad clash lag aachu nanba, paathukalam vidu!")

    async def handle_mention_reply(
        self,
        listener_client: Any,
        message: discord.Message,
    ):
        """
        Triggers natural Discord player replies when any of the 7 active bots
        is explicitly @mentioned or replied to by a human user.
        """
        if message.author.bot or message.author.id in self.orchestrator.bot_user_ids:
            return

        bot_key = listener_client.agent_config.key
        if bot_key not in CASUAL_PLAYER_CHARACTERS:
            return

        clean_text = message.content
        for mention in message.mentions:
            clean_text = clean_text.replace(f"<@{mention.id}>", "").replace(f"<@!{mention.id}>", "")
        clean_text = clean_text.strip()
        if not clean_text:
            clean_text = "wassup"

        try:
            async with message.channel.typing():
                await asyncio.sleep(random.uniform(1.0, 2.0))
                await self.chat(
                    character_key=bot_key,
                    message=clean_text,
                    sender_name=message.author.display_name,
                    channel=message.channel,
                    allow_comeback=True,
                )
        except Exception as exc:
            logger.debug(f"Error handling mention reply for {bot_key}: {exc}")
