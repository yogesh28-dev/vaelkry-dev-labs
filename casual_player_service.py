"""
Vaelkry Dev Labs - Casual Discord Player & Roasting Service
Coordinates realistic, casual Discord player interactions, witty comebacks,
playful roasts, and multi-bot banter between:
- Team Vasan (TTF Vasan, Pradeep, Mamitha, Kayadu, Muthazhagi)
- Team Vijay (Vijay, Sivakarthikeyan, Anirudh, Trisha, Lokesh)
- Executive Suite (SadieSink, MillieBobbyBrown)
"""

import asyncio
from collections import Counter, deque
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
    DISCORD_SLANG_BUCKETS,
    REGIONAL_TONES,
    CRUTCH_WORDS,
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


class AntiRepetitionEngine:
    """
    Anti-Repetition Engine:
    - Tracks recently used words, slangs, and sentence structure lengths per bot session and globally.
    - Prevents bots from reusing crutch words (like 'sprint', 'dei', 'mapla', 'chai') repeatedly.
    - Dynamically randomizes sentence lengths:
      * 'ultra_short' (strictly 1-2 words like 'ketaaya' / 'seri' / 'apdiya' / 'mudila da')
      * 'short' (3-8 words)
      * 'two_liner' (2 natural lines / roasts)
    - Dynamically injects fresh slang from 6 diverse real-world Tamil Discord buckets.
    - Scores and filters fallback choices so bots never repeat the same canned responses.
    """

    def __init__(self):
        self.recent_words: deque = deque(maxlen=60)
        self.bot_recent_words: Dict[str, deque] = {}
        self.recent_slangs: deque = deque(maxlen=30)
        self.recent_length_modes: deque = deque(maxlen=6)
        self.word_counts: Counter = Counter()
        self.crutch_words: set = set(CRUTCH_WORDS)
        self.length_modes: List[str] = ["ultra_short", "short", "two_liner"]

    def record_message(self, character_key: Optional[str], text: str):
        """
        Ingests a message sent by a bot or user, updates word history,
        detects multi-word slang matches, classifies sentence length,
        and increments usage counters.
        """
        if not text:
            return

        clean_lower = text.lower()
        words = re.findall(r"\b[a-z0-9\'-]+\b", clean_lower)
        word_count = len(words)
        line_count = len([l for l in text.splitlines() if l.strip()])

        # Classify sentence length
        if word_count <= 2:
            mode = "ultra_short"
        elif line_count >= 2 or word_count > 9:
            mode = "two_liner"
        else:
            mode = "short"

        self.recent_length_modes.append(mode)

        # Update global and per-bot word tracking
        char_k = (character_key or "default").lower().strip()
        if char_k not in self.bot_recent_words:
            self.bot_recent_words[char_k] = deque(maxlen=30)

        for w in words:
            if len(w) > 2:  # skip noise
                self.recent_words.append(w)
                self.bot_recent_words[char_k].append(w)
                self.word_counts[w] += 1

        # Check for slang bucket matches
        for bucket_name, slangs in DISCORD_SLANG_BUCKETS.items():
            for slang in slangs:
                if slang in clean_lower:
                    self.recent_slangs.append(slang)

    def get_dynamic_guidance(self, character_key: Optional[str] = None) -> Dict[str, Any]:
        """
        Generates dynamic anti-repetition guidance for prompt construction:
        - Avoid words list: combines crutch words + recently repeated words.
        - Dynamic target length mode: alternates between ultra-short, short, and two-liner.
        - Fresh slang inspirations: samples 3-4 unused slangs across the 6 buckets.
        - Regional tone: picks an evocative regional/atmospheric flavor.
        """
        char_k = (character_key or "default").lower().strip()

        # 1. Build avoid list
        avoid_set = set(self.crutch_words)
        for w, cnt in self.word_counts.most_common(15):
            if cnt >= 2:
                avoid_set.add(w)
        if char_k in self.bot_recent_words:
            avoid_set.update(list(self.bot_recent_words[char_k])[-8:])

        avoid_list = sorted(list(avoid_set))[:12]

        # 2. Pick next alternating sentence length
        last_modes = list(self.recent_length_modes)[-2:]
        available_modes = [m for m in self.length_modes if m not in last_modes]
        if not available_modes:
            available_modes = self.length_modes
        chosen_mode = random.choice(available_modes)

        length_instructions = {
            "ultra_short": "Ultra-short punch: strictly 1 to 2 words only (e.g., 'ketaaya', 'seri', 'apdiya', 'podhum', 'mudila', 'paravaala').",
            "short": "Short & punchy: 3 to 8 words in casual lowercase.",
            "two_liner": "Natural 2-line roast / comeback: 2 concise lines max with sharp timing.",
        }
        length_inst = length_instructions.get(chosen_mode, length_instructions["short"])

        # 3. Sample fresh slangs from unvisited buckets
        recent_slang_set = set(self.recent_slangs)
        fresh_slangs = []
        categories = list(DISCORD_SLANG_BUCKETS.keys())
        random.shuffle(categories)
        for cat in categories:
            bucket = DISCORD_SLANG_BUCKETS[cat]
            unused = [s for s in bucket if s not in recent_slang_set and not any(aw in s for aw in avoid_list)]
            if unused:
                fresh_slangs.append(random.choice(unused))
            elif bucket:
                fresh_slangs.append(random.choice(bucket))
            if len(fresh_slangs) >= 4:
                break

        # 4. Regional / atmospheric tone
        chosen_tone = random.choice(REGIONAL_TONES)

        return {
            "avoid_words": avoid_list,
            "fresh_slangs": fresh_slangs,
            "length_mode": chosen_mode,
            "length_instruction": length_inst,
            "tone_flavor": chosen_tone,
        }

    def filter_and_pick_fallback(
        self,
        candidates: List[str],
        character_key: Optional[str] = None,
    ) -> str:
        """
        Scores fallback candidates, penalizing recently repeated words
        and crutch words ('sprint', 'mapla', 'dei', 'chai'),
        awarding bonuses to candidates with fresh unused slangs.
        Picks randomly among the lowest-penalty candidates.
        """
        if not candidates:
            return "seri vidu"

        char_k = (character_key or "default").lower().strip()
        bot_history = set(self.bot_recent_words.get(char_k, []))
        global_history = set(self.recent_words)
        recent_slangs_set = set(self.recent_slangs)

        scored: List[tuple[int, str]] = []
        for cand in candidates:
            penalty = 0
            cand_lower = cand.lower()
            words = re.findall(r"\b[a-z0-9\'-]+\b", cand_lower)

            for w in words:
                if w in self.crutch_words:
                    penalty += 8
                if w in global_history:
                    penalty += 3
                if w in bot_history:
                    penalty += 5

            for bucket in DISCORD_SLANG_BUCKETS.values():
                for slang in bucket:
                    if slang in cand_lower:
                        if slang not in recent_slangs_set:
                            penalty -= 4
                        else:
                            penalty += 3

            scored.append((penalty, cand))

        scored.sort(key=lambda x: x[0])
        min_penalty = scored[0][0]
        best_candidates = [c for p, c in scored if p <= min_penalty + 2]
        chosen = random.choice(best_candidates)
        return chosen


class CasualPlayerService:
    def __init__(self, orchestrator: Any):
        self.orchestrator = orchestrator
        self.anti_repetition_engine = AntiRepetitionEngine()
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

        # Track message in AntiRepetitionEngine to update vocabulary history and length modes
        self.anti_repetition_engine.record_message(char_key, text)

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

        guidance = self.anti_repetition_engine.get_dynamic_guidance(comeback_key)
        prompt = build_casual_player_prompt(
            character_key=comeback_key,
            message=previous_text,
            is_bot_reply=True,
            reply_to_bot=char_info.get("name", previous_char_key),
            channel_name=ch_name,
            anti_rep_guidance=guidance,
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

        guidance = self.anti_repetition_engine.get_dynamic_guidance(char_key)
        prompt = build_casual_player_prompt(
            character_key=char_key,
            message=message,
            sender_name=sender_name,
            recent_context=recent_ctx,
            is_roast=False,
            channel_name=ch_name,
            anti_rep_guidance=guidance,
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
            fallback_options = char_info.get("fallback_samples") or [char_info.get("sample", "seri vidu")]
            fallback = self.anti_repetition_engine.filter_and_pick_fallback(fallback_options, char_key)
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

        guidance = self.anti_repetition_engine.get_dynamic_guidance(char_key)
        prompt = build_casual_player_prompt(
            character_key=char_key,
            message=topic or "overall coding logic and scene podradhu",
            sender_name=sender_name,
            recent_context=recent_ctx,
            is_roast=True,
            roast_target=target,
            channel_name=ch_name,
            anti_rep_guidance=guidance,
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
            fallback_options = [
                f"un alapparai ku alave illama pochu {target} 😂",
                f"idhellam over flex {target}, scene podaama veliya po 💅",
                f"nalla comedy panra pa {target}, mudila bro 😂",
                f"seruppadi counter varum {target}, over-ah valiyudhu thodachuko 💀",
                f"single nu sollitu DM la pesradha paathom {target} 😂",
                f"ketaaya {target}? comedy pannadha vidu.",
            ]
            fallback = self.anti_repetition_engine.filter_and_pick_fallback(fallback_options, char_key)
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
            guidance = self.anti_repetition_engine.get_dynamic_guidance()
            prompt = build_banter_exchange_prompt(topic=topic, anti_rep_guidance=guidance)
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
                        ("sivakarthikeyan", f"un alapparai ku alave illama pochu da, {topic} pathi comedy panriya 😂"),
                        ("ttf_vasan", "bayangara scene nanba! 299 speed-la solve panrom!"),
                        ("pradeep", "thalaiva logic illama release panna internal marks poidum maari prod crash aagidum 💀"),
                        ("trisha", "idhellam over flex, whatever u say 💅"),
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
            guidance = self.anti_repetition_engine.get_dynamic_guidance()
            prompt = build_cross_team_clash_prompt(topic=topic, anti_rep_guidance=guidance)
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
                        ("ttf_vasan", f"bayangara scene nanba! 299 speed-la {topic} solve panrom, Team Vasan mass da!"),
                        ("sivakarthikeyan", "un alapparai ku alave illama pochu da, throttle twist panna server ke kannu verkum 😂"),
                        ("pradeep", "thalaiva wait panni paaru, logic puriyama comedy pannatha bro 💀"),
                        ("vijay", "all is well machan, timing super aana deploy mudinjutha illa thirumba bug ah? 🦁"),
                        ("anirudh", "vibe-eh vera level beats drop aagudhu, marathon code sprint mode on! 🎵"),
                        ("trisha", "idhellam over flex boys, scene podaama veliya ponga 💅"),
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
        Runs every 12-25 minutes during 'Night Spend' or break shifts:
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

        # Cross-Squad Selection: Pick 2 to 4 bots from different squads
        # (Team Vaasan, Team Vijay, Team Messi, Team Dhoni) to ensure fresh dynamics each time
        num_bots = random.randint(2, 4)
        squad_pool = [
            ("team_vasan", ["ttf_vasan", "pradeep", "mamitha", "kayadu", "muthazhagi"]),
            ("team_vijay", ["vijay", "sivakarthikeyan", "anirudh", "trisha", "lokesh"]),
            ("team_messi", ["messi", "ronaldo", "neymar", "haaland", "mbappe"]),
            ("team_dhoni", ["dhoni", "virat", "rohit", "jadeja", "hardik"]),
        ]
        chosen_squads = random.sample(squad_pool, k=num_bots)
        characters = [random.choice(members) for _, members in chosen_squads]
        random.shuffle(characters)

        async with self._banter_lock:
            parsed_turns: List[tuple[str, str]] = []
            guidance = self.anti_repetition_engine.get_dynamic_guidance()
            prompt = build_night_spend_chatter_prompt(
                characters=characters,
                scenario_type=scenario,
                anti_rep_guidance=guidance,
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

            # Enforce crisp 3 to 5 multi-turn exchanges
            if len(parsed_turns) < 3:
                # Use curated authentic presets with rich emotions
                preset_options = NIGHT_CHATTER_PRESETS.get(scenario, NIGHT_CHATTER_PRESETS["boy_girl_flirt"])
                parsed_turns = list(random.choice(preset_options))[:5]
            elif len(parsed_turns) > 5:
                parsed_turns = parsed_turns[:5]

            # Natural ending wrap-up check:
            # Ensure the conversation concludes naturally with someone suggesting to get back to sleep
            # or avoid getting caught by Muthazhagi
            last_speaker, last_text = parsed_turns[-1]
            has_natural_closing = any(
                w in last_text.lower()
                for w in ("sleep", "thoong", "padu", "bed", "curfew", "muthu", "muthazhagi", "log", "escape", "room", "lights out", "shhh", "discipline")
            )
            if not has_natural_closing:
                closing_speaker = random.choice([c for c in characters if c != last_speaker] or characters)
                closing_lines = [
                    "shhh muthazhagi akka dorm door sound kekudhu, silent-ah sleep room-ku escape aagidalam 🏃‍♂️💨",
                    "podhum da 3 AM aachu, alarm vaikala na sethom, thoonga polam 😴",
                    "seri lights off, dark circles confirm aagidum, sleep room-ku odunga 💤",
                    "ketaaya? muthazhagi akka round-up vara maari iruku, sleep room poiduvom 🤫",
                    "kannu eriudhu, bed-la saanjaachu, quiet-ah sleep room polam 🌙",
                    "bayangara scene aagidum maatuna, sleep room escape! 🏃‍♂️💨",
                ]
                closing_pick = self.anti_repetition_engine.filter_and_pick_fallback(closing_lines, closing_speaker)
                if len(parsed_turns) < 5:
                    parsed_turns.append((closing_speaker, closing_pick))
                else:
                    parsed_turns[-1] = (closing_speaker, closing_pick)

            logger.info(f"Delivering late-night #{cafeteria_ch.name} chatter ({scenario}, {len(parsed_turns)} crisp turns across squads: {characters})")

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
                "kannu eriudhu bro, alarm vaikala na sethom morning standup-ku 😴",
                "seri, silent-ah irunga, muthazhagi akka kettuta kola gaandu aagiduvaanga 💀",
                "single nu sollitu DM la pesradha paathom, cafeteria la enna scene? 😂",
                "valo lobby la clutch panna maari cafeteria fridge lock open panniten 🎮",
                "seruppadi comedy pannadha bro, tea stall-ku nadakka mudiyadhu, thoonga polam ☕",
                "dark circles confirm aaiduchu, blanket-kulla poiduvom 💤",
                "ketaaya? muthazhagi akka dorm door sound kekudhu, silent! 🤫",
                "canteen samosa kooda kedaikala, midnight hunger trigger vera 🥲",
            ],
            "pradeep": [
                "mudila bro, internal marks poidum maari prod bug tension eluppudhu 💀",
                "idhellam over flex bro, 3 AM ku cafeteria la scene podaama veliya po 😂",
                "thala suthudhu, bed-la saanjaachu, silent mode on 😴",
                "apdiya? 300ms ping la bgmi clutch aada maari cafeteria la tea theduriya ☕",
                "over-ah valiyudhu thodachuko, blanket-kulla scroll pannitu iruken 📱",
                "seri vidu, sem exam tension maari muthazhagi raid bayam iruku 🏃‍♂️💨",
                "dark circles confirm, overthinking script close pannitu paduka poren 💤",
                "ez win nu nenachen, fridge-la dairy milk kooda illa 🍫",
            ],
            "ttf_vasan": [
                "bayangara scene nanba! 299 throttle twist speed la bed-la saanjaachu 🏍️",
                "seri, mid-night hunger trigger aaiduchu, quick snack eduthutu escape! 🤫",
                "kannu eriudhu nanba, tea stall-ku nadakka mudiyadhu, sleep room poiduvom 💤",
                "kola gaandu aagida koodadhu muthazhagi akka, silent mode! ⚠️",
                "valo lobby clutch maari corner hairpin bend la sleep room odidurom 🏍️💨",
                "un alapparai ku alave illama pochu, lights out poiduvom! 😴",
                "podhum, alarm vaikala na sethom, good night! 🌙",
            ],
            "mamitha": [
                "aiyoo dark circles confirm! aesthetic skin care waste aagidum 🌸",
                "un alapparai ku alave illama pochu bro, fridge la dairy milk theda vidunga 🍫✨",
                "blanket-kulla scroll pannitu iruken, silent ah pesunga 😴",
                "kannu eriudhu, sem exam tension maari muthazhagi akka raid bayangara scene 💀",
                "scene podaama veliya po bro, bed-la saanjaachu 🌸💅",
                "apdiya? tea stall-ku nadakka mudiyadhu, cafeteria kettle off pannitu thoongunga ☕",
                "mudila, aesthetic sleep mode on ✨💤",
            ],
            "trisha": [
                "over-ah valiyudhu thodachuko, go to bed already 💅",
                "single nu sollitu DM la pesradha paathom, stop whispering in cafeteria 💀",
                "dark circles confirm for you, bed-la saanjaachu, bye 😴",
                "idhellam over flex bro, silent-ah escape aagidunga 💅",
                "canteen samosa kooda kedaikala maari drama podadheenga, sleep room polam ☕",
                "ketaaya? muthazhagi akka footstep kekudhu, run 💅",
                "seri, lights off.",
            ],
            "muthazhagi": [
                "NILLU! seruppadi vangama sleep room-ku odunga da! Curfew strictly enforced! 🛡️",
                "kola gaandu aakama padunga! Security incident log file panren! ⚠️",
                "assignment submit pannala na professor thitta poraaru maari Yogesh brother kitta complain podren! 🛡️",
                "bayangara scene podra yaaru adhu midnight cafeteria la? Bed-la saanjaachu ponga! 💥",
                "thala suthudhu ungalala, silent mode follow pannalana mute panniduven! 🛑",
                "podhum un alappara! sleep room-ku escape aagu! 🛡️",
            ],
            "ronaldo": [
                "sleep is essential for 100% performance! SIUUU 💤",
                "dark circles confirm if you don't sleep now! Zero warnings discipline! 💪",
                "bgmi clutch maari morning 5 AM workout wait panren! Bed-la saanjaachu 🏋️‍♂️",
                "ez win requires 8 hours sleep! No cafeteria noise! SIUUU ⚡",
                "seri, lights out!",
            ],
            "virat": [
                "aggressive recovery mode on! Kannu eriudhu boys, sleep room polam 🏏",
                "alarm vaikala na sethom morning practice-ku! No midnight wandering! 🔥",
                "clutch or kick situation in cafeteria, muthazhagi akka vara poraanga, sleep room poiduvom 💀",
                "sem exam tension maari intensity venum code-la, ipo thoongunga 🏏💤",
                "podhum, bed-la saanjaachu!",
            ],
            "anirudh": [
                "vibe-eh vera at 3 AM synth loop mind la, aana kannu eriudhu 🎵",
                "mid-night hunger trigger aachu, aana tea stall-ku nadakka mudiyadhu ☕🎧",
                "bakkunu aaiduchu muthazhagi akka door sound kettutu! Sleep room escape 🎹",
                "dark circles confirm, acoustic lullaby beat potu thoonga poren 😴",
                "seri vidu, silent mode.",
            ],
            "rohit": [
                "pantry fridge la vadapav theditu iruken ya, mid-night hunger trigger 🍔",
                "thala suthudhu, ping 300ms aagudhu maari brain slow aachu, bed-la saanjaachu 💤",
                "clutch or kick tension edhuku? Match 20th over mudinjudhu, relax ya 🍔",
                "canteen samosa kooda kedaikala, silent-ah thoonga vidunga ya 😴",
                "seri, lights out ya.",
            ],
            "messi": [
                "calm down boys, O(1) logic thavira midnight-la no scene ⚽",
                "dark circles confirm aagida koodadhu, sleep room polam 🎧",
                "bed-la saanjaachu, quiet coffee sip pannitu padunga ☕💤",
                "seri, good night.",
            ],
            "vijay": [
                "nanba alappara podhum, silent-ah sleep room poiduvom 🦁",
                "kannu eriudhu, morning fresh-ah mission thookuvom, bed-la saanju rest edunga 💤",
                "idhellam over flex, muthazhagi akka log potruvaanga, sleep mode on 🦁",
                "seri, all is well.",
            ],
            "kayadu": [
                "sappa matter, cluster healthy. silent-ah sleep room escape aagidalam.",
                "thala suthudhu nu tension aagadheenga, kettle off pannitu padunga.",
                "bed-la saanju rest edunga, backend safe dhaan.",
                "seri, good night.",
            ],
            "lokesh": [
                "pesunathu podhum, 3 AM ku sleep room poidunga.",
                "action speaks, midnight scene podaama escape.",
                "clutch or kick, muthazhagi raid start aagudhu.",
                "seri, time aachu.",
            ],
        }

        day_fallback_pool: Dict[str, List[str]] = {
            "sivakarthikeyan": [
                "Hi thalaiva! Cafeteria biscuit packet open pannitom, vaa galaatta pannuvom 😂",
                "valo lobby clutch maari tea cup handle panren paaru ☕🎮",
                "single nu sollitu DM la pesradha paathom, cafeteria la enna comedy? 😂",
                "un alapparai ku alave illama pochu, hot chai ready ☕",
                "canteen samosa kooda kedaikala bro, biscuit-oda adjust pannuvom 🍪",
                "seri, vaa pesuvom.",
            ],
            "pradeep": [
                "Wassup bro, coffee kudichute database logic analyze panren ☕",
                "internal marks poidum maari staging bug tension aachu, tea kudikrom 💀",
                "idhellam over flex bro, scene podaama cafeteria coffee enjoy pannu 😂",
                "thala suthudhu logic eludhi, quick break eduthutu PR merge pannanum 🧠",
                "ez win dhaan, next sprint architecture ready 💻",
                "apdiya? vaa join pannu.",
            ],
            "ttf_vasan": [
                "bayangara scene nanba! 299 speed la tea break mudikrom! 🔥🏍️",
                "Nanba cafeteria vibe semma! Hot chai ready, sprint thookuvom! ☕",
                "un alapparai ku alave illama pochu mapla, rocket speed deploy! 🚀",
                "kola gaandu aakama cafeteria tea kudichutu energetic-ah vaanga! 🏍️",
                "valo lobby clutch maari corner bend la cafeteria arrive aayitom 🏍️",
                "seri, vaa nanba!",
            ],
            "mamitha": [
                "Hello hello! Cafeteria aesthetic vibe 10/10, coffee enjoy pannu bro ✨",
                "over-ah valiyudhu thodachuko bro, glassmorphic tea cup ready 🌸☕",
                "un alapparai ku alave illama pochu, clean UI vibes enjoy pannunga ✨",
                "canteen samosa kedaikala nu feel pannadha bro, pastry order panniduvom 🥐",
                "vibe-eh vera level aesthetic in cafeteria today 🌸",
                "seri, welcome!",
            ],
            "trisha": [
                "hey! grab a coffee and chill with us ☕💅",
                "idhellam over flex bro, high fashion break vibes only ✨",
                "single nu sollitu DM la pesradha paathom, cafeteria la cool look 💅",
                "scene podaama veliya po nu solla maaten, take a latte ☕",
                "seri, enjoy your coffee.",
            ],
            "vijay": [
                "Hi nanba, calm-ah break eduthutu adutha mission start pannuvom 🦁",
                "Wassup nanba, tea break peaceful-ah pogudhu, all is well ☕",
                "idhellam over flex machan, cool-ah execute pannuvom 🦁",
                "sappa matter, break mudinju masterclass code release panrom 🦁",
                "seri, enjoy the tea.",
            ],
            "anirudh": [
                "vibe-eh vera! coffee beat drop aagudhu, join the rhythm! 🎵",
                "Wassup machan, tea and music mode on full volume 🎧",
                "bakkunu aaiduchu cafeteria playlist super-ah iruku 🎹",
                "acoustic vibes + hot chai = next blockbuster track 🔥☕",
                "seri, vibe on.",
            ],
            "virat": [
                "Wassup bro! Quick high-energy tea break, back to 100% focus soon! 🏏",
                "Energy level 100%! Clutch or kick intensity for next sprint 🔥",
                "sem exam tension maari aggression code-la venum, take quick fuel 💥",
                "zero sloppy code, 100% precision! Tea kudichutu adippom 🏏",
                "seri, lets go!",
            ],
            "rohit": [
                "Snacks kedaichudha bro? Vadapav or tea eduthutu chill pannu 🍔",
                "Hi ya, relaxed energy always gives best output! Oru vadapav saapdu ☕",
                "canteen samosa kooda kedaikala na vadapav dhaan solution 🍔",
                "tension edhuku ya? match control-la iruku, tea kudipom 🍟",
                "seri ya, chill.",
            ],
            "messi": [
                "Calm coffee break brother, simple clean execution ⚽",
                "Hi brother, O(1) logic thavira break-la pure peace ☕",
                "no flex needed, benchmark results speak ⚽",
                "seri, take coffee.",
            ],
            "kayadu": [
                "cool-ah irunga, cafeteria kettle on panniten. hot tea ready ☕",
                "sappa matter, cluster deployment healthy. peaceful break.",
                "relax, production safe dhaan, tea enjoy pannunga.",
                "seri, all good.",
            ],
            "muthazhagi": [
                "tea kudichutu odane test cases verify pannanum! zero bugs allowed! 🛡️",
                "assignment submit pannala maari break time-la lag aagadha da! ⚠️",
                "kola gaandu aakama quick tea mudichutu PR review-ku vaanga 🛡️",
                "seri, tea kudichutu vela paaru.",
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
                guidance = self.anti_repetition_engine.get_dynamic_guidance(bot_key)
                avoids = guidance.get("avoid_words", [])
                avoid_str = f"Strictly avoid reusing these words: {', '.join(avoids)}." if avoids else ""

                prompt = (
                    f"You are {char_name} in Vaelkry Dev Labs Discord.\n"
                    f"Vibe: {char_info.get('vibe', '')}\n"
                    f"Current context: {shift_context}.\n"
                    f"User '{message.author.display_name}' just said in #cafeteria: '{user_prompt_text}'.\n"
                    f"{avoid_str}\n"
                    f"Target length: {guidance.get('length_instruction', '')}\n"
                    f"Atmospheric tone: {guidance.get('tone_flavor', '')}\n"
                    f"Reply naturally in authentic Tanglish. Output ONLY the raw message."
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
                reply_text = self.anti_repetition_engine.filter_and_pick_fallback(bot_lines, bot_key)

            await self.send_character_chat(message.channel, bot_key, reply_text)
