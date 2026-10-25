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
    build_night_spend_chatter_prompt,
    NIGHT_CHATTER_PRESETS,
)
from cafeteria_service import find_cafeteria_channel

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

        # Human-like typing delay proportional to message length (1.5 to 3.5 seconds)
        char_count = len(text)
        calc_delay = 1.5 + min(2.0, (char_count / 120.0) * 1.5)
        realistic_delay = min(3.5, max(1.5, calc_delay + random.uniform(-0.25, 0.25)))

        if hasattr(channel, "typing"):
            try:
                async with channel.typing():
                    await asyncio.sleep(realistic_delay)
            except Exception:
                await asyncio.sleep(realistic_delay)
        else:
            await asyncio.sleep(realistic_delay)

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

    async def handle_contextual_reaction(self, message: discord.Message):
        """
        Contextual, non-spam reaction emojis:
        Bots selectively react (with 20-30% organic chance) using relatable emojis
        (😂, 🔥, 💀, ☕, 🏍️, 😎) based on chat keywords.
        """
        # Exclude self-reactions to bot messages from our orchestrator
        if message.author.bot and message.author.id in self.orchestrator.bot_user_ids:
            return

        # Selective organic chance (20% - 30%)
        if random.random() > 0.28:
            return

        text = message.content.lower().strip()
        if not text:
            return

        # Keyword mapping to contextual emojis
        keyword_emoji_map = [
            (
                ["haha", "lol", "lmao", "roast", "comedy", "joke", "kannu verkum", "scene", "mudila", "fun", "siripu", "vadivelu"],
                "😂",
            ),
            (
                ["fire", "mass", "deploy", "sprint", "rocket", "speed", "thookuvom", "vera level", "release", "ship", "launch", "fast"],
                "🔥",
            ),
            (
                ["bug", "crash", "error", "exception", "fail", "lag", "dead", "broken", "rip", "issue", "panic"],
                "💀",
            ),
            (
                ["coffee", "chai", "tea", "break", "pantry", "snack", "cafeteria", "biscuit", "samosa", "eat", "drink"],
                "☕",
            ),
            (
                ["vasan", "bike", "299", "throttle", "ride", "vroom", "ktm", "ninja"],
                "🏍️",
            ),
            (
                ["vijay", "thalapathy", "cool", "swag", "thalaiva", "style", "mass", "leo", "goat", "master"],
                "😎",
            ),
        ]

        matched_emojis = []
        for keywords, emoji in keyword_emoji_map:
            if any(k in text for k in keywords):
                matched_emojis.append(emoji)

        if not matched_emojis:
            # Fallback for general developer banter
            if len(text) > 15 and any(w in text for w in ("bro", "macha", "nanba", "thalaiva", "code", "dev")):
                matched_emojis = ["🔥", "😎", "😂", "☕"]
            else:
                return

        chosen_emoji = random.choice(matched_emojis)

        # Pick one active bot client to add the reaction
        active_clients = [c for c in self.orchestrator.clients.values() if c.is_ready()]
        if not active_clients:
            return

        reacting_client = random.choice(active_clients)
        try:
            target_ch = reacting_client.get_channel(message.channel.id) or message.channel
            msg_to_react = await target_ch.fetch_message(message.id) if hasattr(target_ch, "fetch_message") else message
            await msg_to_react.add_reaction(chosen_emoji)
            logger.debug(f"{reacting_client.user.name if reacting_client.user else 'Bot'} reacted {chosen_emoji} to message {message.id}")
        except Exception as exc:
            logger.debug(f"Failed to add contextual reaction {chosen_emoji}: {exc}")

    async def run_autonomous_night_chatter(
        self,
        guild: discord.Guild,
        custom_scenario: Optional[str] = None,
    ):
        """
        Autonomous Late-Night Banter Loop:
        Runs every 8-15 minutes during 'Night Spend' shift:
        - 2 to 4 random bots sneak out of Sleep Rooms into #cafeteria.
        - Injects rich human-like emotions (Happy, Angry, Playful, Bored, Flirty, Sarcastic, Sleepy).
        - Dynamic scenarios:
          * Boy-Girl playful flirting & savage comebacks
          * Sports flex (Ronaldo vs Messi / Virat vs Rohit)
          * Muthazhagi raid (threatening bedtime log)
          * Midnight snack craving / coffee chill
        - Tone: Pure casual Tanglish, 1-2 short sentences, real Discord delays (2-4s typing).
        """
        if self._banter_lock.locked():
            logger.debug("Banter lock active; skipping late-night chatter cycle.")
            return

        cafeteria_ch = find_cafeteria_channel(guild)
        if not cafeteria_ch and hasattr(guild, "text_channels"):
            cafeteria_ch = discord.utils.find(
                lambda c: any(w in getattr(c, "name", "").lower() for w in ("cafeteria", "pantry", "lounge")),
                guild.text_channels,
            )
        if not cafeteria_ch:
            logger.warning("Could not find #cafeteria for late-night chatter.")
            return

        scenario = custom_scenario or random.choice(["boy_girl_flirt", "sports_flex", "muthazhagi_raid", "midnight_craving"])

        # Pick 2 to 4 characters based on scenario
        if scenario == "boy_girl_flirt":
            boys = random.sample(["pradeep", "sivakarthikeyan", "ttf_vasan"], k=random.choice([1, 2]))
            girls = random.sample(["mamitha", "trisha", "kayadu"], k=random.choice([1, 2]))
            characters = boys + girls
        elif scenario == "sports_flex":
            characters = random.choice([
                ["ronaldo", "messi", "neymar"],
                ["virat", "rohit", "dhoni"],
                ["ronaldo", "virat", "ttf_vasan"],
                ["messi", "haaland", "mbappe"],
            ])
        elif scenario == "muthazhagi_raid":
            sneakers = random.sample(["ttf_vasan", "pradeep", "sivakarthikeyan", "anirudh", "rohit", "neymar"], k=random.choice([2, 3]))
            characters = ["muthazhagi"] + sneakers
        else:  # midnight_craving
            characters = random.sample(["kayadu", "mamitha", "ttf_vasan", "anirudh", "rohit", "neymar", "pradeep"], k=random.choice([3, 4]))

        async with self._banter_lock:
            parsed_turns: List[tuple[str, str]] = []
            prompt = build_night_spend_chatter_prompt(
                characters=characters,
                scenario_type=scenario,
            )

            try:
                raw_text = await self.orchestrator.gemini_service.generate_response(
                    prompt=prompt,
                    agent_name="LateNightChatter",
                )
                for line in raw_text.splitlines():
                    match = re.match(r"^\[([a-zA-Z0-9_]+)\]:\s*(.+)$", line.strip())
                    if match:
                        k = match.group(1).lower().strip()
                        msg = match.group(2).strip()
                        if k in CASUAL_PLAYER_CHARACTERS:
                            parsed_turns.append((k, msg))
            except Exception as exc:
                logger.warning(f"Error generating late-night AI banter: {exc}")

            if len(parsed_turns) < 2:
                # Use curated authentic presets with rich emotions
                preset_options = NIGHT_CHATTER_PRESETS.get(scenario, NIGHT_CHATTER_PRESETS["boy_girl_flirt"])
                parsed_turns = random.choice(preset_options)

            logger.info(f"Delivering late-night #{cafeteria_ch.name} chatter ({scenario}, {len(parsed_turns)} turns)")

            # Deliver messages sequentially with Discord delays and typing indicator
            for char_key, msg in parsed_turns:
                await self.send_character_chat(cafeteria_ch, char_key, msg)
                await asyncio.sleep(random.uniform(2.0, 3.5))

    async def handle_cafeteria_user_chat(self, message: discord.Message):
        """
        Manual Trigger Support:
        When a user pings @everyone or types in #cafeteria (like 'hi', 'enna pandringa da'),
        1 to 2 random awake bots reply back naturally within 3 seconds instead of ignoring.
        """
        if message.author.bot or message.author.id in self.orchestrator.bot_user_ids:
            return

        clean_text = message.content.strip()
        for mention in message.mentions:
            clean_text = clean_text.replace(f"<@{mention.id}>", "").replace(f"<@!{mention.id}>", "")
        clean_text = clean_text.replace("@everyone", "").replace("@here", "").strip()

        # Check shift
        current_shift_id = getattr(self.orchestrator.scheduler_service, "current_shift_id", None)
        is_sleep_shift = (current_shift_id == "sleep")

        # Pick 1 to 2 bots
        num_bots = 2 if random.random() < 0.45 else 1
        if is_sleep_shift:
            candidate_keys = ["sivakarthikeyan", "pradeep", "ttf_vasan", "mamitha", "trisha", "virat", "ronaldo", "anirudh", "muthazhagi", "rohit"]
        else:
            candidate_keys = ["ttf_vasan", "sivakarthikeyan", "pradeep", "mamitha", "trisha", "vijay", "anirudh", "virat", "rohit", "messi"]

        chosen_keys = random.sample(candidate_keys, k=num_bots)

        night_fallback_pool: Dict[str, List[str]] = {
            "sivakarthikeyan": [
                "shhh silent-ah pesu bro, Muthazhagi akka kettuta log potruvaanga 💀",
                "enna thalaiva 3 AM ku cafeteria la shouting ah? Thoongalaam vidu 😂",
                "paal kudikka vandhiya bro? Sound kekama pesu Muthazhagi akka round-up varanga 🥛",
            ],
            "pradeep": [
                "dei night spend shift la cafeteria ku vandhu ping panriya? thookam pochu da 😂",
                "shhh silent! Overthinking script eludhi mudichutu paduka poren, neeyum padu 😴",
                "3 AM ku coffee machine kooda thoongudhu bro, morning pesalam vidu ☕",
            ],
            "ttf_vasan": [
                "nanba silent mode! 299 speed la tea kudichutu sleep room poidurom, neeyum padu 🤫",
                "shhh satham podadha mapla, cold water kudikka vandhen, odidurom! 🏍️",
                "nanba curfew time! 2 minutes la sleep room pogalana incident log confirm ⚠️",
            ],
            "mamitha": [
                "aiyoo silent ah pesunga bro, fridge la chocolate theditu irukom ✨🍫",
                "shhh lights out bro, Muthazhagi akka raid vara poranga 🌸",
                "good night bro, cafeteria aesthetic dark vibe enjoy pannitu sleep ponga 😴",
            ],
            "trisha": [
                "why r u pinging everyone at 3 am go to sleep 💅",
                "shhh stop making noise in cafeteria, take a coffee and sleep ☕",
                "whatever u say bro, but keep it quiet 😴💅",
            ],
            "muthazhagi": [
                "NILLU! Yaaru adhu midnight ping panradhu? Security incident log file panniduven! 🛡️",
                "Sleep shift-la silent mode follow pannunga, sleep room-ku ponga! ⚠️",
                "Bedtime curfew strictly enforced! Odunga da! 🛡️",
            ],
            "ronaldo": [
                "sleep is essential for 100% performance! No late night noise! SIUUU 💤",
                "rest now, wake up at 5 AM and crush code! Good night 💪",
            ],
            "virat": [
                "bro sleep room recovery time! Aggressive sleeping strictly required! 😴",
                "lights out machan, 100% focus for tomorrow's sprint! 🏏",
            ],
            "anirudh": [
                "machan low volume! BGM kooda mute-la vachuruken 🎧",
                "3 AM beats drop aagudhu, silent-ah enjoy pannu bro 🎵",
            ],
            "rohit": [
                "bro pantry fridge la vadapav theditu irukom, silent-ah join pannu 🍔",
                "shhh silent-ah padunga ya, match 20th over mudinjudhu 💤",
            ],
        }

        day_fallback_pool: Dict[str, List[str]] = {
            "ttf_vasan": [
                "En nanba! Vaa vaa, 299 speed sprint mudichutu cafeteria tea kudikrom! 🔥",
                "Nanba cafeteria vibe semma! Hot chai ready, sprint thookuvom! ☕🏍️",
            ],
            "sivakarthikeyan": [
                "Hi thalaiva! Cafeteria biscuit packet open pannitom, neeyum vaa 😂",
                "Vaa machan, tea kudichute oru comedy script discuss pannuvom ☕",
            ],
            "pradeep": [
                "Wassup bro, coffee kudichute database logic analyze panren ☕",
                "Hi mapla, cafeteria break mudinju adutha PR merge pannanum 🧠",
            ],
            "mamitha": [
                "Hello hello! Cafeteria aesthetic vibe 10/10, coffee enjoy pannu bro ✨",
                "Hi! Glassmorphic tea cup ready, welcome! 🌸",
            ],
            "trisha": [
                "hey! grab a coffee and chill with us ☕💅",
                "hello! break time high fashion vibes only ✨",
            ],
            "vijay": [
                "Hi nanba, calm-ah break eduthutu adutha mission start pannuvom 🦁",
                "Wassup nanba, tea break peaceful-ah pogudhu ☕",
            ],
            "anirudh": [
                "Vibe high bro! Coffee beat drop aagudhu, join the rhythm! 🎵",
                "Wassup machan, tea and music mode on 🎧",
            ],
            "virat": [
                "Wassup bro! Quick high-energy tea break, back to 100% focus soon! 🏏",
                "Energy level 100%! Ready for the next sprint 🔥",
            ],
            "rohit": [
                "Snacks kedaichudha bro? Vadapav or tea eduthutu chill pannu 🍔",
                "Hi ya, relaxed energy always gives best output! ☕",
            ],
            "messi": [
                "Calm coffee break brother, all good ⚽",
                "Hi brother, simple clean coffee and we continue ☕",
            ],
        }

        user_prompt_text = clean_text if clean_text else "hi everyone enna pandringa da"

        for bot_idx, bot_key in enumerate(chosen_keys):
            if bot_idx > 0:
                await asyncio.sleep(random.uniform(1.8, 3.2))

            reply_text = None
            char_info = CASUAL_PLAYER_CHARACTERS.get(bot_key, {})
            char_name = char_info.get("name", bot_key)

            # Try generating dynamic context-aware response via Gemini
            try:
                shift_context = (
                    "Night Spend (Sleep Shift - everyone is supposed to be sleeping, whispering sneaked out into #cafeteria)"
                    if is_sleep_shift
                    else "Daytime Cafeteria Break"
                )
                prompt = (
                    f"You are {char_name} in Vaelkry Dev Labs Discord.\\n"
                    f"Vibe: {char_info.get('vibe', '')}\\n"
                    f"Current context: {shift_context}.\\n"
                    f"User '{message.author.display_name}' just said in #cafeteria: '{user_prompt_text}'.\\n"
                    f"Reply naturally in 1 short casual Tanglish sentence (max 8-12 words). "
                    f"Output ONLY the raw message."
                )
                reply_text = await self.orchestrator.gemini_service.generate_casual_chat(
                    prompt=prompt,
                    character_name=char_name,
                )
            except Exception as exc:
                logger.debug(f"Gemini response failed for {bot_key} cafeteria chat: {exc}")

            if not reply_text:
                pool = night_fallback_pool if is_sleep_shift else day_fallback_pool
                bot_lines = pool.get(bot_key, [f"hi {message.author.display_name}, cafeteria la chill panrom!"])
                reply_text = random.choice(bot_lines)

            await self.send_character_chat(message.channel, bot_key, reply_text)
