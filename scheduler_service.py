"""
Vaelkry Dev Labs - Multi-Agent Enterprise Discord System
Company Scheduler & 24h IST Shift Routine Engine
Orchestrates shift rotations, voice cabin movements, sleep routines, and staggered voice handshakes.
"""

import asyncio
import datetime
import logging
import random
from typing import Dict, List, Optional, Tuple

import discord
import pytz

logger = logging.getLogger("VaelkryDevLabs.Scheduler")

IST = pytz.timezone("Asia/Kolkata")

CEO_NOTIFICATION_CHANNEL_NAME = "yogesh-chat"
CEO_NOTIFICATION_CHANNEL_ID = 1563622902744481812

EXECUTIVE_BOT_KEYS = {"sadie", "millie"}

SQUAD_MAPPINGS = {
    "team_vasan": ["ttf_vasan", "pradeep", "mamitha", "kayadu", "muthazhagi"],
    "team_vijay": ["vijay", "sivakarthikeyan", "anirudh", "trisha", "lokesh"],
    "team_messi": ["messi", "ronaldo", "neymar", "haaland", "mbappe"],
    "team_dhoni": ["dhoni", "virat", "rohit", "jadeja", "hardik"],
    "team_elon": ["elon", "mrbeast", "steve_jobs", "bill_gates", "kevin_mitnick"],
    "team_tony": ["tony", "tom_cruise", "brad_pitt", "johnny_depp", "walter_white"],
}


def _normalize_bot_key(key: str) -> str:
    return key.lower().replace("bot_token_", "").replace("-", "_").strip()


def is_ceo_vc(channel: Optional[discord.VoiceChannel]) -> bool:
    if not channel:
        return False
    name = channel.name.lower()
    return "ceo" in name or "executive" in name


def get_ceo_channel(guild: discord.Guild) -> Optional[discord.TextChannel]:
    ch = guild.get_channel(CEO_NOTIFICATION_CHANNEL_ID)
    if isinstance(ch, discord.TextChannel):
        return ch
    for c in guild.text_channels:
        if c.name.lower() == CEO_NOTIFICATION_CHANNEL_NAME:
            return c
    return None


class CompanyScheduler:
    def __init__(self, orchestrator):
        self.orchestrator = orchestrator
        self.is_active = True
        self.voice_override_active = False
        self._voice_connect_lock = asyncio.Lock()
        self._scheduler_task: Optional[asyncio.Task] = None

    async def start(self, guild: discord.Guild) -> str:
        self.is_active = True
        if not self._scheduler_task or self._scheduler_task.done():
            self._scheduler_task = asyncio.create_task(self._run_schedule_loop(guild))
        return "🚀 **Vaelkry Dev Labs Company Operations & 24h IST Scheduler Activated!**"

    async def stop(self, guild: discord.Guild) -> str:
        self.is_active = False
        if self._scheduler_task and not self._scheduler_task.done():
            self._scheduler_task.cancel()
        await self.disconnect_all_bots(guild)
        return "🛑 **Vaelkry Dev Labs Company Operations Paused & Bots Disconnected from Voice.**"

    def get_status_embed(self, guild: discord.Guild) -> discord.Embed:
        now_ist = datetime.datetime.now(IST)
        embed = discord.Embed(
            title="📊 Vaelkry Dev Labs — Operational Status",
            description=f"**Current IST Time:** `{now_ist.strftime('%Y-%m-%d %H:%M:%S IST')}`\n"
                        f"**Scheduler State:** `{'ACTIVE' if self.is_active else 'PAUSED'}`\n"
                        f"**Voice Override:** `{'ACTIVE' if self.voice_override_active else 'INACTIVE'}`\n"
                        f"**Connected Clients:** `{len(self.orchestrator.clients)}/32 Bots`",
            color=0x2ECC71 if self.is_active else 0xE74C3C,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        return embed

    async def notify_ceo_channel(self, guild: discord.Guild, embed: discord.Embed):
        ch = get_ceo_channel(guild)
        if ch:
            try:
                await ch.send(embed=embed)
            except Exception as e:
                logger.warning(f"Failed to post to CEO channel: {e}")

    async def handle_bot_login_voice(self, bot_key: str, client: discord.Client, guild: discord.Guild):
        """
        Safely auto-joins assigned working cabin on bot login.
        Uses a random jitter delay and an asyncio lock to completely prevent
        simultaneous Discord gateway rate limits and websocket connection resets.
        """
        # Staggered entry delay to smooth out traffic burst
        jitter = random.uniform(2.0, 8.0)
        await asyncio.sleep(jitter)

        if not self.is_active:
            return

        clean_key = _normalize_bot_key(bot_key)

        # Skip executive escorts from auto-joining dev squad cabins
        if clean_key in EXECUTIVE_BOT_KEYS:
            return

        async with self._voice_connect_lock:
            try:
                target_vc = self._find_bot_target_working_vc(clean_key, guild)
                if not target_vc:
                    return

                # Check if client is already inside the correct VC
                current_vc = None
                guild_me = guild.get_member(client.user.id) if client.user else None
                if guild_me and guild_me.voice:
                    current_vc = guild_me.voice.channel

                if current_vc and current_vc.id == target_vc.id:
                    return

                # Check for existing voice protocol
                voice_client = discord.utils.get(client.voice_clients, guild=guild)
                if voice_client and voice_client.is_connected():
                    await voice_client.move_to(target_vc)
                else:
                    await target_vc.connect(timeout=25.0, reconnect=True)

                # Unmute and undeafen immediately
                if hasattr(client, "ws") and client.ws:
                    await client.ws.voice_state(guild.id, target_vc.id, self_mute=False, self_deaf=False)

                logger.info(f"[{clean_key}] Connected safely to {target_vc.name} (Category: {target_vc.category.name if target_vc.category else 'None'})")
                
                # Small cool-off before releasing lock for next bot
                await asyncio.sleep(1.2)
            except discord.errors.ClientException as c_err:
                logger.debug(f"Client already active or busy for {clean_key}: {c_err}")
            except Exception as exc:
                logger.warning(f"Safe voice handshake retry for {clean_key}: {exc}")

    def _find_bot_target_working_vc(self, bot_key: str, guild: discord.Guild) -> Optional[discord.VoiceChannel]:
        """Maps character to their squad category and assigns Working Vc 1."""
        target_squad = "team_vasan"
        for squad, members in SQUAD_MAPPINGS.items():
            if bot_key in members:
                target_squad = squad
                break

        squad_names = {
            "team_vasan": "Team Vaasan",
            "team_vijay": "Team Vijay",
            "team_messi": "Team Messi",
            "team_dhoni": "Team Dhoni",
            "team_elon": "Team Elon",
            "team_tony": "Team Tony",
        }
        category_name = squad_names.get(target_squad, "Team Vaasan").lower()

        matched_cat = discord.utils.find(
            lambda c: c.name.strip().lower() == category_name,
            guild.categories,
        )

        if matched_cat:
            vc = discord.utils.find(
                lambda v: "working vc 1" in v.name.lower(),
                matched_cat.voice_channels,
            )
            if not vc and matched_cat.voice_channels:
                vc = matched_cat.voice_channels[0]
            if vc:
                return vc

        # Fallback to Tech Cafe or first voice channel
        for c in guild.voice_channels:
            if "working" in c.name.lower() or "byte" in c.name.lower():
                return c

        return guild.voice_channels[0] if guild.voice_channels else None

    async def wake_all_bots_to_vc(
        self,
        guild: discord.Guild,
        target_vc: Optional[discord.VoiceChannel] = None,
    ) -> Tuple[int, discord.VoiceChannel]:
        """Gathers all available bots into the destination VC with randomized human jitter."""
        self.voice_override_active = True

        resolved_vc = target_vc
        if not resolved_vc:
            for vc in guild.voice_channels:
                if "the hangout zone" in vc.name.lower() or "byte & bit" in vc.name.lower() or "working vc 1" in vc.name.lower():
                    resolved_vc = vc
                    break
        if not resolved_vc and guild.voice_channels:
            resolved_vc = guild.voice_channels[0]

        if not resolved_vc:
            raise RuntimeError("No voice channel found in server.")

        count = 0
        for key, client in self.orchestrator.clients.items():
            if not client.is_ready():
                continue

            asyncio.create_task(self._staggered_move_bot(client, resolved_vc, guild, key))
            count += 1

        return count, resolved_vc

    async def _staggered_move_bot(
        self,
        client: discord.Client,
        target_vc: discord.VoiceChannel,
        guild: discord.Guild,
        bot_key: str,
    ):
        delay = random.uniform(0.8, 6.0)
        await asyncio.sleep(delay)
        async with self._voice_connect_lock:
            try:
                voice_client = discord.utils.get(client.voice_clients, guild=guild)
                if voice_client and voice_client.is_connected():
                    await voice_client.move_to(target_vc)
                else:
                    await target_vc.connect(timeout=20.0, reconnect=True)

                if hasattr(client, "ws") and client.ws:
                    await client.ws.voice_state(guild.id, target_vc.id, self_mute=False, self_deaf=False)

                await asyncio.sleep(0.5)
            except Exception as e:
                logger.debug(f"Failed staggered join for {bot_key}: {e}")

    async def evict_unauthorized_bots_from_ceo_vc(self, guild: discord.Guild):
        """Strictly ensures no non-executive bots stay in CEO VC."""
        ceo_vc = discord.utils.find(lambda c: is_ceo_vc(c), guild.voice_channels)
        if not ceo_vc:
            return

        for member in list(ceo_vc.members):
            if member.bot:
                bot_key = self.orchestrator.bot_user_ids.get(member.id, "")
                clean_k = _normalize_bot_key(bot_key)
                if clean_k not in EXECUTIVE_BOT_KEYS:
                    try:
                        # Move unauthorized bot out to their working VC or disconnect
                        target_vc = self._find_bot_target_working_vc(clean_k, guild)
                        if target_vc and target_vc.id != ceo_vc.id:
                            await member.move_to(target_vc)
                        else:
                            await member.move_to(None)
                        logger.info(f"Evicted unauthorized bot '{member.name}' from CEO VC.")
                    except Exception as ev_err:
                        logger.debug(f"Could not evict bot {member.name}: {ev_err}")

    async def trigger_movie_hangout(self, guild: discord.Guild) -> Tuple[bool, str]:
        """Moves 2-3 dev bots into The Hangout Zone for movie watch session."""
        hangout_vc = discord.utils.find(
            lambda c: "the hangout zone" in c.name.lower() or "hangout" in c.name.lower(),
            guild.voice_channels,
        )
        if not hangout_vc:
            return False, "⚠️ Channel `The Hangout Zone` not found."

        picked_devs = random.sample(
            ["ttf_vasan", "vijay", "messi", "dhoni", "elon", "tony", "pradeep", "sivakarthikeyan", "mrbeast"],
            3,
        )
        for dev_k in picked_devs:
            cl = self.orchestrator.clients.get(dev_k)
            if cl and cl.is_ready():
                asyncio.create_task(self._staggered_move_bot(cl, hangout_vc, guild, dev_k))

        names = ", ".join(f"`{k}`" for k in picked_devs)
        return True, f"🍿 **Movie hangout activated in {hangout_vc.mention}!** Moved bots: {names}."

    async def disconnect_all_bots(self, guild: discord.Guild):
        for client in self.orchestrator.clients.values():
            voice_client = discord.utils.get(client.voice_clients, guild=guild)
            if voice_client and voice_client.is_connected():
                try:
                    await voice_client.disconnect(force=True)
                except Exception:
                    pass

    async def _run_schedule_loop(self, guild: discord.Guild):
        while self.is_active:
            try:
                await asyncio.sleep(60.0)
                # Routine shift synchronization (checks every minute)
                if not self.voice_override_active:
                    await self._sync_shift_routine(guild)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Error in scheduler routine loop: {e}")
                await asyncio.sleep(15.0)

    async def _sync_shift_routine(self, guild: discord.Guild):
        """Enforces shift rotations based on current IST time."""
        now_ist = datetime.datetime.now(IST)
        hour = now_ist.hour

        # Example: 00:00 to 07:00 IST Night Spend / Sleep mode
        if 0 <= hour < 7:
            sleep_cat = discord.utils.find(lambda c: "night spend" in c.name.lower(), guild.categories)
            if sleep_cat and sleep_cat.voice_channels:
                dest_vc = sleep_cat.voice_channels[0]
                for key, client in self.orchestrator.clients.items():
                    clean_k = _normalize_bot_key(key)
                    if clean_k in EXECUTIVE_BOT_KEYS:
                        continue
                    v_client = discord.utils.get(client.voice_clients, guild=guild)
                    if v_client and v_client.is_connected() and v_client.channel.id != dest_vc.id:
                        await v_client.move_to(dest_vc)
                        if hasattr(client, "ws") and client.ws:
                            await client.ws.voice_state(guild.id, dest_vc.id, self_mute=True, self_deaf=True)