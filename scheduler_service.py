"""
Vaelkry Dev Labs - Company Lifecycle & IST Routine Scheduler
Manages company operation states (/start and /stop) and executes the automated
24-hour Indian Standard Time (IST - Asia/Kolkata) shift routine for all 5 Team Vaasan bots.
Includes multi-room distributed sleeping across the "Night Spend" category.
"""

import asyncio
import datetime
import logging
import random
from dataclasses import dataclass
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo
import discord

logger = logging.getLogger("VaelkryDevLabs.Scheduler")

# Dedicated CEO Notification Channel definitions
CEO_NOTIFICATION_CHANNEL_ID: int = 1563622902744481812
CEO_NOTIFICATION_CHANNEL_NAME: str = "yogesh-chat"


def get_ceo_channel(guild: discord.Guild) -> Optional[discord.TextChannel]:
    """
    Retrieves the dedicated CEO operational notification channel (yogesh-chat).
    1. Strictly checks guild.get_channel(1563622902744481812).
    2. Fallbacks to searching for a text channel named 'yogesh-chat'.
    Ensures company operational notifications, shift updates, and status logs
    are never routed to #announcements.
    """
    ch = guild.get_channel(CEO_NOTIFICATION_CHANNEL_ID)
    if ch and isinstance(ch, discord.TextChannel):
        return ch

    return discord.utils.find(
        lambda c: c.name.lower() == CEO_NOTIFICATION_CHANNEL_NAME.lower() and isinstance(c, discord.TextChannel),
        guild.text_channels,
    )


@dataclass
class ShiftDefinition:
    shift_id: str
    name: str
    category_name: str
    vc_name: str
    self_mute: bool
    self_deaf: bool
    activity_name: str
    start_hour: int
    end_hour: int  # exclusive, unless start > end (wraps midnight)


# 11 distinct routine shifts covering the full 24-hour cycle
ROUTINE_SHIFTS: List[ShiftDefinition] = [
    ShiftDefinition(
        shift_id="sleep",
        name="Sleep (Night Spend)",
        category_name="Night Spend",
        vc_name="Sleep Room 1",  # Base room, distributed dynamically across all Night Spend rooms
        self_mute=True,
        self_deaf=True,
        activity_name="Sleeping in Night Spend 💤",
        start_hour=17,
        end_hour=2,
    ),
    ShiftDefinition(
        shift_id="warmup",
        name="Warmup (Tech Cafe)",
        category_name="Tech Cafe",
        vc_name="The Hangout Zone",
        self_mute=False,
        self_deaf=False,
        activity_name="Chai & Coffee ☕",
        start_hour=2,
        end_hour=3,
    ),
    ShiftDefinition(
        shift_id="work_1",
        name="Work Shift 1 (Team Vaasan)",
        category_name="Team Vaasan",
        vc_name="Working Vc 1",
        self_mute=False,
        self_deaf=False,
        activity_name="Sprint 1 - System Dev 💻",
        start_hour=3,
        end_hour=5,
    ),
    ShiftDefinition(
        shift_id="break_1",
        name="Rest Break 1 (Tech Cafe)",
        category_name="Tech Cafe",
        vc_name="The Seven Slide",
        self_mute=False,
        self_deaf=False,
        activity_name="Break - Gaming 🎮",
        start_hour=5,
        end_hour=6,
    ),
    ShiftDefinition(
        shift_id="work_2",
        name="Work Shift 2 (Team Vaasan)",
        category_name="Team Vaasan",
        vc_name="Working Vc 2",
        self_mute=False,
        self_deaf=False,
        activity_name="Sprint 2 - Code & Logic ⚙️",
        start_hour=6,
        end_hour=8,
    ),
    ShiftDefinition(
        shift_id="break_2",
        name="Rest Break 2 (Tech Cafe)",
        category_name="Tech Cafe",
        vc_name="Byte & Bit",
        self_mute=False,
        self_deaf=False,
        activity_name="Breakfast & Refreshment 🥪",
        start_hour=8,
        end_hour=9,
    ),
    ShiftDefinition(
        shift_id="work_3",
        name="Work Shift 3 (Team Vaasan)",
        category_name="Team Vaasan",
        vc_name="Working Vc 1",
        self_mute=False,
        self_deaf=False,
        activity_name="Sprint 3 - UI Components 🎨",
        start_hour=9,
        end_hour=11,
    ),
    ShiftDefinition(
        shift_id="break_3",
        name="Rest Break 3 (Tech Cafe)",
        category_name="Tech Cafe",
        vc_name="The Hive",
        self_mute=False,
        self_deaf=False,
        activity_name="Power Nap ⚡",
        start_hour=11,
        end_hour=12,
    ),
    ShiftDefinition(
        shift_id="work_4",
        name="Work Shift 4 (Team Vaasan)",
        category_name="Team Vaasan",
        vc_name="Working Vc 2",
        self_mute=False,
        self_deaf=False,
        activity_name="Sprint 4 - APIs & Infra 🚢",
        start_hour=12,
        end_hour=14,
    ),
    ShiftDefinition(
        shift_id="break_4",
        name="Rest Break 4 (Tech Cafe)",
        category_name="Tech Cafe",
        vc_name="The Hangout Zone",
        self_mute=False,
        self_deaf=False,
        activity_name="Lunch & Arcade Break 🍛",
        start_hour=14,
        end_hour=15,
    ),
    ShiftDefinition(
        shift_id="work_5",
        name="Work Shift 5 (Team Vaasan)",
        category_name="Team Vaasan",
        vc_name="Working Vc 1",
        self_mute=False,
        self_deaf=False,
        activity_name="Sprint 5 - QA & Wrap 🛡️",
        start_hour=15,
        end_hour=17,
    ),
]


def get_current_ist_time() -> datetime.datetime:
    """Returns the current timezone-aware timestamp in Asia/Kolkata (IST)."""
    try:
        return datetime.datetime.now(ZoneInfo("Asia/Kolkata"))
    except Exception:
        ist_tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30), name="IST")
        return datetime.datetime.now(ist_tz)


def match_current_shift(now_ist: datetime.datetime) -> ShiftDefinition:
    """Determines which shift is active based on the current IST hour."""
    hour = now_ist.hour
    for shift in ROUTINE_SHIFTS:
        if shift.start_hour > shift.end_hour:
            if hour >= shift.start_hour or hour < shift.end_hour:
                return shift
        else:
            if shift.start_hour <= hour < shift.end_hour:
                return shift

    return ROUTINE_SHIFTS[0]


class CompanyScheduler:
    """
    Coordinates lifecycle states (/start and /stop) and executes the 1-minute
    background loop moving Team Vaasan and Team Vijay bots according to IST shifts.
    """

    def __init__(self, orchestrator: "AgentOrchestrator"):
        self.orchestrator = orchestrator
        self.team_vasan_keys: List[str] = ["ttf_vasan", "pradeep", "mamitha", "kayadu", "muthazhagi"]
        self.team_vijay_keys: List[str] = ["vijay", "sivakarthikeyan", "anirudh", "trisha", "lokesh"]
        self.team_keys: List[str] = self.team_vasan_keys  # Backward compatibility
        self.is_active: bool = False
        self.current_shift_id: Optional[str] = None
        self._loop_task: Optional[asyncio.Task] = None
        self.assigned_sleep_rooms: Dict[str, int] = {}  # agent_key -> voice_channel_id
        self.assigned_cafe_rooms: Dict[str, int] = {}   # agent_key -> voice_channel_id

    @property
    def all_dev_keys(self) -> List[str]:
        """Returns all developer bot keys across Team Vaasan and Team Vijay."""
        return self.team_vasan_keys + self.team_vijay_keys

    async def get_night_spend_voice_channels(self, guild: discord.Guild) -> List[discord.VoiceChannel]:
        """
        Dynamically fetches all voice channels under the 'Night Spend' category.
        Falls back to any voice channels containing 'sleep' or auto-provisions if none exist.
        """
        night_spend_cat = discord.utils.find(
            lambda c: c.name.strip().lower() == "night spend",
            guild.categories,
        )
        if night_spend_cat and night_spend_cat.voice_channels:
            return list(night_spend_cat.voice_channels)

        # Fallback 1: Voice channels in guild with 'sleep' in the name
        sleep_vcs = [vc for vc in guild.voice_channels if "sleep" in vc.name.lower()]
        if sleep_vcs:
            return sleep_vcs

        # Fallback 2: Auto-provision Night Spend category with Sleep Room 1, 2, 3
        try:
            if not night_spend_cat:
                night_spend_cat = await guild.create_category(name="Night Spend")
            r1 = await night_spend_cat.create_voice_channel(name="Sleep Room 1")
            r2 = await night_spend_cat.create_voice_channel(name="Sleep Room 2")
            r3 = await night_spend_cat.create_voice_channel(name="Sleep Room 3")
            return [r1, r2, r3]
        except Exception as exc:
            logger.error(f"Error provisioning fallback sleep rooms: {exc}")
            if guild.voice_channels:
                return [guild.voice_channels[0]]
            return []

    async def get_tech_cafe_voice_channels(self, guild: discord.Guild) -> List[discord.VoiceChannel]:
        """
        Dynamically fetches all 4 voice channels under the 'Tech Cafe' category:
        'The Seven Slide', 'Byte & Bit', 'The Hive', 'The Hangout Zone'.
        Auto-provisions or searches by name if category is missing.
        """
        tech_cafe_cat = discord.utils.find(
            lambda c: c.name.strip().lower() == "tech cafe",
            guild.categories,
        )
        if tech_cafe_cat and tech_cafe_cat.voice_channels:
            return list(tech_cafe_cat.voice_channels)

        expected_names = ["The Seven Slide", "Byte & Bit", "The Hive", "The Hangout Zone"]
        # Fallback 1: match by name across guild
        found = [vc for vc in guild.voice_channels if vc.name.strip().lower() in [n.lower() for n in expected_names]]
        if found:
            return found

        # Fallback 2: auto-provision Tech Cafe category with all 4 rooms
        try:
            if not tech_cafe_cat:
                tech_cafe_cat = await guild.create_category(name="Tech Cafe")
            vcs = []
            for name in expected_names:
                vc = discord.utils.find(lambda v: v.name.strip().lower() == name.lower(), tech_cafe_cat.voice_channels)
                if not vc:
                    vc = await tech_cafe_cat.create_voice_channel(name=name)
                vcs.append(vc)
            return vcs
        except Exception as exc:
            logger.error(f"Error provisioning fallback Tech Cafe channels: {exc}")
            if guild.voice_channels:
                return [guild.voice_channels[0]]
            return []

    async def find_or_provision_voice_channel(
        self,
        guild: discord.Guild,
        category_name: str,
        vc_name: str,
    ) -> Optional[discord.VoiceChannel]:
        """
        Dynamically searches for a voice channel within a category,
        falling back to guild-wide search or auto-provisioning if missing.
        """
        category = discord.utils.find(
            lambda c: c.name.strip().lower() == category_name.strip().lower(),
            guild.categories,
        )
        if category:
            vc = discord.utils.find(
                lambda v: v.name.strip().lower() == vc_name.strip().lower(),
                category.voice_channels,
            )
            if vc:
                return vc
            if category.voice_channels:
                return category.voice_channels[0]

        vc = discord.utils.find(
            lambda v: v.name.strip().lower() == vc_name.strip().lower(),
            guild.voice_channels,
        )
        if vc:
            return vc

        try:
            if not category:
                category = await guild.create_category(name=category_name)
            new_vc = await category.create_voice_channel(name=vc_name)
            logger.info(f"Auto-provisioned missing VC '{vc_name}' under '{category_name}'")
            return new_vc
        except Exception as exc:
            logger.error(f"Failed to provision fallback voice channel '{vc_name}': {exc}")
            if guild.voice_channels:
                return guild.voice_channels[0]
            return None

    async def move_single_bot(
        self,
        client: discord.Client,
        target_vc: discord.VoiceChannel,
        shift: ShiftDefinition,
    ):
        """Moves a single bot to target_vc, updates mute/deaf, and sets custom activity."""
        guild = client.get_guild(target_vc.guild.id) or target_vc.guild
        bot_member = guild.me or guild.get_member(client.user.id)

        # 1. Set custom status activity
        try:
            activity = discord.CustomActivity(name=shift.activity_name)
            await client.change_presence(activity=activity)
        except Exception as exc:
            logger.warning(f"Failed to update activity for {client.user.name}: {exc}")

        # 2. Strict mute/deaf determination:
        # Enforce False for all non-sleep shifts or when inside Tech Cafe / Working VCs
        is_sleep = (shift.shift_id == "sleep")
        target_mute = True if is_sleep else False
        target_deaf = True if is_sleep else False

        vc_name_lower = target_vc.name.lower()
        cat_name_lower = target_vc.category.name.lower() if target_vc.category else ""
        if "sleep" not in vc_name_lower and "night spend" not in cat_name_lower:
            target_mute = False
            target_deaf = False

        # 3. Voice connection and mute/deaf state update
        is_in_voice = bool(bot_member and bot_member.voice and bot_member.voice.channel)
        voice_client = discord.utils.get(client.voice_clients, guild=guild)

        try:
            if is_in_voice or (voice_client and voice_client.is_connected()):
                # Already in voice on Discord: change channel and mute/deaf via gateway
                await guild.change_voice_state(
                    channel=target_vc,
                    self_mute=target_mute,
                    self_deaf=target_deaf,
                )
            else:
                if voice_client:
                    try:
                        await voice_client.disconnect(force=True)
                    except Exception:
                        pass
                await target_vc.connect(
                    self_mute=target_mute,
                    self_deaf=target_deaf,
                    reconnect=True,
                )
        except discord.errors.ClientException as ce:
            logger.info(f"ClientException for {client.user.name} ({ce}). Falling back to gateway state change...")
            try:
                await guild.change_voice_state(
                    channel=target_vc,
                    self_mute=target_mute,
                    self_deaf=target_deaf,
                )
            except Exception as e2:
                logger.warning(f"Gateway change_voice_state fallback failed for {client.user.name}: {e2}")
        except Exception as exc:
            logger.warning(f"Voice state update failed for {client.user.name}: {exc}. Retrying...")
            try:
                await guild.change_voice_state(
                    channel=target_vc,
                    self_mute=target_mute,
                    self_deaf=target_deaf,
                )
            except Exception as retry_exc:
                logger.error(f"Failed to connect {client.user.name} to {target_vc.name}: {retry_exc}")

        # 4. Strictly enforce gateway ws.voice_state directly:
        # await bot_instance.ws.voice_state(guild.id, vc.id, self_mute=False, self_deaf=False)
        try:
            if hasattr(client, "ws") and client.ws:
                await client.ws.voice_state(
                    guild.id,
                    target_vc.id,
                    self_mute=target_mute,
                    self_deaf=target_deaf,
                )
        except Exception as ws_err:
            logger.debug(f"Direct ws.voice_state update for {client.user.name}: {ws_err}")

    async def apply_shift(self, guild: discord.Guild, shift: ShiftDefinition):
        """Applies the specified shift to Team Vaasan and Team Vijay bots concurrently."""
        now_ist = get_current_ist_time()
        logger.info(f"Applying Shift: [{shift.name}] at {now_ist.strftime('%H:%M:%S IST')}")

        move_tasks = []

        if shift.shift_id == "sleep":
            # ==================== SLEEP SHIFT (DISTRIBUTED ACROSS NIGHT SPEND) ====================
            self.assigned_cafe_rooms.clear()
            sleep_channels = await self.get_night_spend_voice_channels(guild)
            if not sleep_channels:
                logger.error("No sleep voice channels found in Night Spend.")
                return

            logger.info(
                f"Distributing developer bots across {len(sleep_channels)} Night Spend room(s): "
                f"{[vc.name for vc in sleep_channels]}"
            )

            # Balanced random distribution across available sleep rooms
            shuffled_rooms = list(sleep_channels)
            random.shuffle(shuffled_rooms)

            self.assigned_sleep_rooms.clear()
            for idx, key in enumerate(self.all_dev_keys):
                client = self.orchestrator.clients.get(key)
                if not client or not client.is_ready():
                    continue

                assigned_vc = shuffled_rooms[idx % len(shuffled_rooms)]
                self.assigned_sleep_rooms[key] = assigned_vc.id
                logger.info(f"Sleep assignment: {client.user.name} -> {assigned_vc.name} (Night Spend)")
                move_tasks.append(self.move_single_bot(client, assigned_vc, shift))

        elif (
            shift.category_name.strip().lower() == "tech cafe"
            or shift.shift_id.startswith("break")
            or shift.shift_id == "warmup"
        ):
            # ==================== TECH CAFE BREAK / WARMUP SHIFTS (BALANCED RANDOM) ====================
            # Clear sleep assignments
            self.assigned_sleep_rooms.clear()

            cafe_channels = await self.get_tech_cafe_voice_channels(guild)
            if not cafe_channels:
                logger.error("No voice channels found under Tech Cafe.")
                return

            logger.info(
                f"Randomly distributing developer bots across {len(cafe_channels)} Tech Cafe room(s): "
                f"{[vc.name for vc in cafe_channels]}"
            )

            # Randomly shuffle Tech Cafe voice channels so bots are NOT dumped into 'The Hive'
            shuffled_cafe = list(cafe_channels)
            random.shuffle(shuffled_cafe)

            self.assigned_cafe_rooms.clear()
            for idx, key in enumerate(self.all_dev_keys):
                client = self.orchestrator.clients.get(key)
                if not client or not client.is_ready():
                    continue

                assigned_vc = shuffled_cafe[idx % len(shuffled_cafe)]
                self.assigned_cafe_rooms[key] = assigned_vc.id
                logger.info(f"Tech Cafe assignment: {client.user.name} -> {assigned_vc.name} (Tech Cafe)")
                move_tasks.append(self.move_single_bot(client, assigned_vc, shift))

        else:
            # ==================== ACTIVE SPRINT / WORKING SHIFTS ====================
            self.assigned_sleep_rooms.clear()
            self.assigned_cafe_rooms.clear()

            # 1. Team Vaasan Cabin
            vasan_vc = await self.find_or_provision_voice_channel(
                guild=guild,
                category_name=shift.category_name,
                vc_name=shift.vc_name,
            )
            if vasan_vc:
                logger.info(f"Relocating Team Vaasan bots together to '{vasan_vc.name}' ({shift.category_name})")
                for key in self.team_vasan_keys:
                    client = self.orchestrator.clients.get(key)
                    if client and client.is_ready():
                        move_tasks.append(self.move_single_bot(client, vasan_vc, shift))

            # 2. Team Vijay Cabin ('Team Vijay' -> 'Working Vc 1')
            vijay_vc = await self.find_or_provision_voice_channel(
                guild=guild,
                category_name="Team Vijay",
                vc_name="Working Vc 1",
            )
            if vijay_vc:
                logger.info(f"Relocating Team Vijay bots to '{vijay_vc.name}' (Team Vijay)")
                for key in self.team_vijay_keys:
                    client = self.orchestrator.clients.get(key)
                    if client and client.is_ready():
                        move_tasks.append(self.move_single_bot(client, vijay_vc, shift))

        if move_tasks:
            await asyncio.gather(*move_tasks, return_exceptions=True)

        self.current_shift_id = shift.shift_id

    def get_ceo_channel(self, guild: discord.Guild) -> Optional[discord.TextChannel]:
        """
        Retrieves the dedicated CEO operational notification channel (yogesh-chat).
        Strictly targets Channel ID 1563622902744481812 with fallback search by name 'yogesh-chat'.
        """
        return get_ceo_channel(guild)

    async def notify_ceo_channel(
        self,
        guild: discord.Guild,
        content: Optional[str] = None,
        embed: Optional[discord.Embed] = None,
    ):
        """
        Sends operational status notifications and embeds exclusively to the CEO channel (yogesh-chat).
        Guarantees that no automated alerts ever post to #announcements.
        """
        ceo_ch = self.get_ceo_channel(guild)
        if not ceo_ch:
            logger.warning(
                f"CEO channel ({CEO_NOTIFICATION_CHANNEL_NAME} / {CEO_NOTIFICATION_CHANNEL_ID}) not found in guild."
            )
            return

        lead_client = self.orchestrator.clients.get("ttf_vasan")
        target_ch = lead_client.get_channel(ceo_ch.id) if lead_client else ceo_ch
        if not target_ch:
            target_ch = ceo_ch

        try:
            kwargs = {}
            if content:
                kwargs["content"] = content
            if embed:
                kwargs["embed"] = embed
            if kwargs:
                await target_ch.send(**kwargs)
        except Exception as exc:
            logger.warning(f"Failed to post notification to #{ceo_ch.name}: {exc}")

    def get_status_embed(self, guild: discord.Guild) -> discord.Embed:
        """
        Generates a live operational status log embed for Vaelkry Dev Labs.
        Summarizes current IST time, active shift, scheduler state, and VC locations for
        both Team Vaasan and Team Vijay.
        """
        now_ist = get_current_ist_time()
        shift = match_current_shift(now_ist) if self.is_active else None

        embed = discord.Embed(
            title="📊 Vaelkry Dev Labs — Squad Operational Status",
            color=discord.Color.brand_green() if self.is_active else discord.Color.greyple(),
            timestamp=now_ist,
        )
        embed.add_field(name="Current IST Time", value=f"`{now_ist.strftime('%H:%M:%S IST')}`", inline=True)
        embed.add_field(
            name="Scheduler Loop",
            value="🟢 **Active (1m loop)**" if self.is_active else "🔴 **Paused**",
            inline=True,
        )

        if self.is_active and shift:
            embed.add_field(name="Active Routine Shift", value=f"**{shift.name}**", inline=True)
            embed.add_field(name="Prescribed Activity", value=f"`{shift.activity_name}`", inline=False)
            embed.add_field(
                name="Voice State Flags",
                value=f"`self_mute={shift.self_mute}`, `self_deaf={shift.self_deaf}`",
                inline=True,
            )

        # Team Vaasan location breakdown
        vasan_lines = []
        for key in self.team_vasan_keys:
            client = self.orchestrator.clients.get(key)
            name = client.agent_config.name if (client and hasattr(client, "agent_config")) else key
            bot_guild = client.get_guild(guild.id) if client else guild
            bot_member = (bot_guild.me or bot_guild.get_member(client.user.id)) if (client and client.user and bot_guild) else None
            vc = bot_member.voice.channel if (bot_member and bot_member.voice) else None
            loc_str = f"🔊 `{vc.name}`" if vc else "*(Offline / Disconnected)*"
            vasan_lines.append(f"• **{name}:** {loc_str}")

        embed.add_field(
            name="Team Vaasan Real-Time VC Locations",
            value="\n".join(vasan_lines) if vasan_lines else "No bots online",
            inline=False,
        )

        # Team Vijay location breakdown
        vijay_lines = []
        for key in self.team_vijay_keys:
            client = self.orchestrator.clients.get(key)
            name = client.agent_config.name if (client and hasattr(client, "agent_config")) else key
            bot_guild = client.get_guild(guild.id) if client else guild
            bot_member = (bot_guild.me or bot_guild.get_member(client.user.id)) if (client and client.user and bot_guild) else None
            vc = bot_member.voice.channel if (bot_member and bot_member.voice) else None
            loc_str = f"🔊 `{vc.name}`" if vc else "*(Offline / Disconnected)*"
            vijay_lines.append(f"• **{name}:** {loc_str}")

        embed.add_field(
            name="Team Vijay Real-Time VC Locations",
            value="\n".join(vijay_lines) if vijay_lines else "No bots online",
            inline=False,
        )

        ceo_ch = self.get_ceo_channel(guild)
        ceo_mention = ceo_ch.mention if ceo_ch else f"#{CEO_NOTIFICATION_CHANNEL_NAME}"
        embed.set_footer(
            text=f"CEO Notifications Only: {CEO_NOTIFICATION_CHANNEL_NAME} ({CEO_NOTIFICATION_CHANNEL_ID}) • #announcements kept clean"
        )
        return embed

    async def _run_loop(self, guild: discord.Guild):
        """Continuous 1-minute background loop monitoring IST shift transitions."""
        logger.info("IST Routine Scheduler background loop started.")
        while self.is_active:
            try:
                now_ist = get_current_ist_time()
                current_shift = match_current_shift(now_ist)

                # Check if shift changed
                if current_shift.shift_id != self.current_shift_id:
                    logger.info(f"IST Shift Transition Detected: {current_shift.name}")
                    await self.apply_shift(guild, current_shift)

                    # Send shift transition embed strictly to #yogesh-chat
                    if current_shift.shift_id == "sleep" and self.assigned_sleep_rooms:
                        room_lines = []
                        for k, rid in self.assigned_sleep_rooms.items():
                            client = self.orchestrator.clients.get(k)
                            ch = guild.get_channel(rid)
                            name = client.user.name if (client and client.user) else k
                            room_name = ch.name if ch else "Sleep Room"
                            room_lines.append(f"  • **{name}:** 🔊 `{room_name}`")

                        shift_embed = discord.Embed(
                            title=f"🌙 [SHIFT UPDATE] Sleep (Night Spend) — {now_ist.strftime('%H:%M IST')}",
                            description=(
                                "**All developer bots dispersed across Night Spend rooms:**\n"
                                + "\n".join(room_lines)
                                + "\n\n• **Voice State:** `self_mute=True`, `self_deaf=True`"
                                + "\n• **Custom Status:** `Sleeping in Night Spend 💤`"
                            ),
                            color=discord.Color.purple(),
                            timestamp=now_ist,
                        )
                        shift_embed.set_footer(
                            text=f"CEO Channel Exclusive: #{CEO_NOTIFICATION_CHANNEL_NAME} • Clean #announcements"
                        )
                    elif (
                        current_shift.category_name.strip().lower() == "tech cafe"
                        or current_shift.shift_id.startswith("break")
                        or current_shift.shift_id == "warmup"
                    ) and self.assigned_cafe_rooms:
                        room_lines = []
                        for k, rid in self.assigned_cafe_rooms.items():
                            client = self.orchestrator.clients.get(k)
                            ch = guild.get_channel(rid)
                            name = client.user.name if (client and client.user) else k
                            room_name = ch.name if ch else "Tech Cafe"
                            room_lines.append(f"  • **{name}:** 🔊 `{room_name}`")

                        shift_embed = discord.Embed(
                            title=f"☕ [SHIFT UPDATE] {current_shift.name} — {now_ist.strftime('%H:%M IST')}",
                            description=(
                                "**Developer bots distributed across Tech Cafe rooms (The Seven Slide, Byte & Bit, The Hive, The Hangout Zone):**\n"
                                + "\n".join(room_lines)
                                + f"\n\n• **Prescribed Activity:** `{current_shift.activity_name}`"
                                + "\n• **Voice State:** `self_mute=False`, `self_deaf=False` (Undeafened & Unmuted)"
                            ),
                            color=discord.Color.gold(),
                            timestamp=now_ist,
                        )
                        shift_embed.set_footer(
                            text=f"CEO Channel Exclusive: #{CEO_NOTIFICATION_CHANNEL_NAME} • Clean #announcements"
                        )
                    else:
                        shift_embed = discord.Embed(
                            title=f"🔔 [SHIFT UPDATE] {current_shift.name} — {now_ist.strftime('%H:%M IST')}",
                            description=(
                                f"• **Team Vaasan:** Relocated to `🔊 {current_shift.vc_name}` ({current_shift.category_name})\n"
                                f"• **Team Vijay:** Relocated to `🔊 Working Vc 1` (Team Vijay)\n"
                                f"• **Prescribed Activity:** `{current_shift.activity_name}`\n"
                                f"• **Voice State:** `self_mute=False`, `self_deaf=False` (Undeafened & Unmuted)"
                            ),
                            color=discord.Color.blue(),
                            timestamp=now_ist,
                        )
                        shift_embed.set_footer(
                            text=f"CEO Channel Exclusive: #{CEO_NOTIFICATION_CHANNEL_NAME} • Clean #announcements"
                        )

                    await self.notify_ceo_channel(guild, embed=shift_embed)

                    # Dispatch lively rest-break notice to #cafeteria
                    if current_shift.shift_id in ("warmup", "rest_1", "rest_2", "rest_3", "rest_4"):
                        if hasattr(self.orchestrator, "cafeteria_service") and self.orchestrator.cafeteria_service:
                            asyncio.create_task(
                                self.orchestrator.cafeteria_service.notify_shift_break(
                                    guild, current_shift.name, current_shift.vc_name
                                )
                            )

                else:
                    # Periodic alignment check
                    if current_shift.shift_id == "sleep" and self.assigned_sleep_rooms:
                        # Ensure each bot stays in its assigned sleep room without bouncing
                        for key, room_id in self.assigned_sleep_rooms.items():
                            client = self.orchestrator.clients.get(key)
                            target_vc = guild.get_channel(room_id)
                            if client and client.is_ready() and target_vc:
                                vc_conn = discord.utils.get(client.voice_clients, guild=guild)
                                bot_member = guild.me or guild.get_member(client.user.id)
                                is_in_target = (
                                    (vc_conn and vc_conn.is_connected() and vc_conn.channel.id == target_vc.id)
                                    or (bot_member and bot_member.voice and bot_member.voice.channel and bot_member.voice.channel.id == target_vc.id)
                                )
                                if not is_in_target:
                                    asyncio.create_task(self.move_single_bot(client, target_vc, current_shift))
                    elif (
                        current_shift.category_name.strip().lower() == "tech cafe"
                        or current_shift.shift_id.startswith("break")
                        or current_shift.shift_id == "warmup"
                    ) and self.assigned_cafe_rooms:
                        # Ensure bots remain in their assigned Tech Cafe room without bouncing
                        for key, room_id in self.assigned_cafe_rooms.items():
                            client = self.orchestrator.clients.get(key)
                            target_vc = guild.get_channel(room_id)
                            if client and client.is_ready() and target_vc:
                                vc_conn = discord.utils.get(client.voice_clients, guild=guild)
                                bot_member = guild.me or guild.get_member(client.user.id)
                                is_in_target = (
                                    (vc_conn and vc_conn.is_connected() and vc_conn.channel.id == target_vc.id)
                                    or (bot_member and bot_member.voice and bot_member.voice.channel and bot_member.voice.channel.id == target_vc.id)
                                )
                                if not is_in_target:
                                    asyncio.create_task(self.move_single_bot(client, target_vc, current_shift))
                    else:
                        # Active work shift alignment
                        vasan_vc = await self.find_or_provision_voice_channel(
                            guild, current_shift.category_name, current_shift.vc_name
                        )
                        vijay_vc = await self.find_or_provision_voice_channel(
                            guild, "Team Vijay", "Working Vc 1"
                        )
                        if vasan_vc:
                            for key in self.team_vasan_keys:
                                client = self.orchestrator.clients.get(key)
                                if client and client.is_ready():
                                    vc_conn = discord.utils.get(client.voice_clients, guild=guild)
                                    bot_member = guild.me or guild.get_member(client.user.id)
                                    is_in_target = (
                                        (vc_conn and vc_conn.is_connected() and vc_conn.channel.id == vasan_vc.id)
                                        or (bot_member and bot_member.voice and bot_member.voice.channel and bot_member.voice.channel.id == vasan_vc.id)
                                    )
                                    if not is_in_target:
                                        asyncio.create_task(self.move_single_bot(client, vasan_vc, current_shift))
                        if vijay_vc:
                            for key in self.team_vijay_keys:
                                client = self.orchestrator.clients.get(key)
                                if client and client.is_ready():
                                    vc_conn = discord.utils.get(client.voice_clients, guild=guild)
                                    bot_member = guild.me or guild.get_member(client.user.id)
                                    is_in_target = (
                                        (vc_conn and vc_conn.is_connected() and vc_conn.channel.id == vijay_vc.id)
                                        or (bot_member and bot_member.voice and bot_member.voice.channel and bot_member.voice.channel.id == vijay_vc.id)
                                    )
                                    if not is_in_target:
                                        asyncio.create_task(self.move_single_bot(client, vijay_vc, current_shift))
            except asyncio.CancelledError:
                logger.info("Scheduler background loop cancelled.")
                break
            except Exception as exc:
                logger.exception(f"Error in scheduler background loop: {exc}")

            await asyncio.sleep(60)

    async def start(self, guild: discord.Guild) -> str:
        """
        Activates the company lifecycle:
        1. Posts operational start status embed strictly to #yogesh-chat (1563622902744481812).
        2. Evaluates current IST time and immediately relocates developer bots.
        3. Starts the 1-minute scheduler background loop.
        """
        if self.is_active:
            return "⚠️ **Company is already in active operation!** The IST scheduler is running."

        self.is_active = True
        now_ist = get_current_ist_time()
        initial_shift = match_current_shift(now_ist)

        # Immediately apply current IST shift
        await self.apply_shift(guild, initial_shift)

        # Launch 1-minute routine loop
        if self._loop_task and not self._loop_task.done():
            self._loop_task.cancel()
        self._loop_task = asyncio.create_task(self._run_loop(guild))

        # Build informative location summary
        if initial_shift.shift_id == "sleep" and self.assigned_sleep_rooms:
            room_lines = []
            for k, rid in self.assigned_sleep_rooms.items():
                client = self.orchestrator.clients.get(k)
                ch = guild.get_channel(rid)
                name = client.user.name if client and client.user else k
                room_name = ch.name if ch else "Sleep Room"
                room_lines.append(f"  • **{name}:** 🔊 `{room_name}`")
            vc_display = "Distributed across Night Spend rooms:\n" + "\n".join(room_lines)
        elif (
            initial_shift.category_name.strip().lower() == "tech cafe"
            or initial_shift.shift_id.startswith("break")
            or initial_shift.shift_id == "warmup"
        ) and self.assigned_cafe_rooms:
            room_lines = []
            for k, rid in self.assigned_cafe_rooms.items():
                client = self.orchestrator.clients.get(k)
                ch = guild.get_channel(rid)
                name = client.user.name if client and client.user else k
                room_name = ch.name if ch else "Tech Cafe"
                room_lines.append(f"  • **{name}:** 🔊 `{room_name}`")
            vc_display = "Randomly distributed across Tech Cafe rooms:\n" + "\n".join(room_lines)
        else:
            vc_display = (
                f"• Team Vaasan: `🔊 {initial_shift.vc_name}` ({initial_shift.category_name})\n"
                f"• Team Vijay: `🔊 Working Vc 1` (Team Vijay)"
            )

        ceo_ch = self.get_ceo_channel(guild)
        ceo_mention = ceo_ch.mention if ceo_ch else f"#{CEO_NOTIFICATION_CHANNEL_NAME}"

        # Post rich operational start embed strictly to CEO channel (yogesh-chat)
        start_embed = discord.Embed(
            title="🚀 Vaelkry Dev Labs — Active Operation Started",
            description=(
                "**Vaelkry Dev Labs is now officially in active operation!**\n"
                "Both Team Vaasan and Team Vijay bots are adhering to IST shift guidelines.\n\n"
                f"• **Operational Logs & Alerts:** Routed strictly to {ceo_mention}\n"
                f"• **#announcements Status:** Kept strictly clean for official manual CEO announcements\n"
                "• **Voice State Enforcement:** Strictly unmuted and undeafened during all working and break shifts!"
            ),
            color=discord.Color.brand_green(),
            timestamp=now_ist,
        )
        start_embed.add_field(name="Current IST Time", value=f"`{now_ist.strftime('%H:%M:%S IST')}`", inline=True)
        start_embed.add_field(name="Initial Active Shift", value=f"**{initial_shift.name}**", inline=True)
        start_embed.add_field(name="Assigned Locations", value=vc_display, inline=False)
        start_embed.add_field(name="Status Presence", value=f"`{initial_shift.activity_name}`", inline=False)
        if guild.icon:
            start_embed.set_thumbnail(url=guild.icon.url)
        start_embed.set_footer(
            text=f"CEO Channel Exclusive: #{CEO_NOTIFICATION_CHANNEL_NAME} ({CEO_NOTIFICATION_CHANNEL_ID}) • Vaelkry Dev Labs HQ"
        )

        await self.notify_ceo_channel(guild, embed=start_embed)

        return (
            f"🚀 **Vaelkry Dev Labs Operations Started!**\n"
            f"• **Current Time:** `{now_ist.strftime('%H:%M:%S IST')}`\n"
            f"• **Current Shift:** `{initial_shift.name}`\n"
            f"• **Assigned Location:**\n{vc_display}\n"
            f"• **Status:** `{initial_shift.activity_name}`\n"
            f"• **Operational Logs:** Routed exclusively to {ceo_mention} (#announcements kept clean)!\n"
            f"Both Team Vaasan and Team Vijay are aligned and the IST scheduler loop is active! ⚡"
        )

    async def stop(self, guild: discord.Guild) -> str:
        """
        Deactivates company operations:
        1. Cancels scheduler loop.
        2. Disconnects developer bots from voice channels cleanly.
        3. Posts pause notice embed exclusively to #yogesh-chat (1563622902744481812).
        """
        if not self.is_active:
            return "ℹ️ **Vaelkry Dev Labs is already paused.**"

        self.is_active = False

        if self._loop_task and not self._loop_task.done():
            self._loop_task.cancel()
            self._loop_task = None

        self.current_shift_id = None
        self.assigned_sleep_rooms.clear()
        self.assigned_cafe_rooms.clear()

        # Cleanly disconnect all developer bots and set standby presence
        disconnect_tasks = []
        for key in self.all_dev_keys:
            client = self.orchestrator.clients.get(key)
            if client:
                for vc in list(client.voice_clients):
                    disconnect_tasks.append(vc.disconnect(force=True))

                bot_guild = client.get_guild(guild.id) or guild
                if bot_guild and bot_guild.me and bot_guild.me.voice:
                    disconnect_tasks.append(bot_guild.change_voice_state(channel=None))

                disconnect_tasks.append(
                    client.change_presence(activity=discord.CustomActivity(name="Operations Paused ⏸️"))
                )

        if disconnect_tasks:
            await asyncio.gather(*disconnect_tasks, return_exceptions=True)

        now_ist = get_current_ist_time()
        ceo_ch = self.get_ceo_channel(guild)
        ceo_mention = ceo_ch.mention if ceo_ch else f"#{CEO_NOTIFICATION_CHANNEL_NAME}"

        # Post rich pause alert embed strictly to CEO channel (yogesh-chat)
        pause_embed = discord.Embed(
            title="⏸️ Vaelkry Dev Labs — Operations Paused",
            description=(
                "**Vaelkry Dev Labs operations paused by CEO.**\n"
                "• Routine scheduler background loop deactivated.\n"
                "• Team Vaasan & Team Vijay bots disconnected cleanly from voice channels.\n"
                "• Presences reset to `Operations Paused ⏸️`.\n\n"
                f"• Alert posted exclusively in {ceo_mention} (#announcements kept clean)."
            ),
            color=discord.Color.orange(),
            timestamp=now_ist,
        )
        pause_embed.add_field(name="Paused At", value=f"`{now_ist.strftime('%H:%M:%S IST')}`", inline=True)
        pause_embed.add_field(name="Squads Voice State", value="`Disconnected from VC`", inline=True)
        if guild.icon:
            pause_embed.set_thumbnail(url=guild.icon.url)
        pause_embed.set_footer(
            text=f"CEO Channel Exclusive: #{CEO_NOTIFICATION_CHANNEL_NAME} ({CEO_NOTIFICATION_CHANNEL_ID}) • Vaelkry Dev Labs HQ"
        )

        await self.notify_ceo_channel(guild, embed=pause_embed)

        return (
            "⏸️ **Vaelkry Dev Labs Operations Paused!**\n"
            "• Routine scheduler loop deactivated.\n"
            "• Team Vaasan & Team Vijay bots disconnected cleanly from voice channels.\n"
            f"• Notice posted exclusively in {ceo_mention} (#announcements kept clean)."
        )

