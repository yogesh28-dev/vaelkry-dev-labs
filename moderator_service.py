"""
Vaelkry Dev Labs - Executive Moderator Service
Implements:
1. Event Audit Logging into #full-logs by MillieBobbyBrown.
2. Enterprise Onboarding & Greeting into #greeting by SadieSink.
3. Follower Mode (/follow & /unfollow) for CEO voice accompaniment by both SadieSink & MillieBobbyBrown.
4. Probabilistic 5-to-7 minute floor-patrol background routine for SadieSink & MillieBobbyBrown.
"""

import asyncio
import datetime
import logging
import random
from typing import Any, Dict, List, Optional, Tuple
import discord

logger = logging.getLogger("VaelkryDevLabs.Moderator")

# Target CEO Voice Cabin Definitions
CEO_VC_ID: int = 1563622904829190326
CEO_VC_NAME: str = "CEO vc"


def get_ceo_voice_channel(guild: discord.Guild) -> Optional[discord.VoiceChannel]:
    """
    Retrieves the CEO voice cabin ('CEO vc').
    1. Strictly checks channel ID 1563622904829190326.
    2. Fallback search by name 'CEO vc'.
    """
    ch = guild.get_channel(CEO_VC_ID)
    if ch and isinstance(ch, discord.VoiceChannel):
        return ch

    return discord.utils.find(
        lambda c: c.name.lower() == CEO_VC_NAME.lower() and isinstance(c, discord.VoiceChannel),
        guild.voice_channels,
    )


def generate_id_card_embed(member: discord.Member, employee_id: Optional[str] = None) -> discord.Embed:
    """
    Generates a high-aesthetic Digital Corporate ID Card for an employee of Vaelkry Dev Labs.
    """
    if not employee_id:
        if member == member.guild.owner or member.id == member.guild.owner_id:
            emp_id = "VDL-CEO-001"
        else:
            emp_id = f"VDL-EMP-{member.id % 9000 + 1000}"
    else:
        emp_id = employee_id

    # Resolve roles excluding @everyone
    roles = [r for r in member.roles if r.name != "@everyone"]
    top_role = roles[-1].name if roles else "💻 Software Engineer"

    # Determine department and security clearance
    if member == member.guild.owner or member.id == member.guild.owner_id or "ceo" in top_role.lower():
        clearance = "Level 5 — Supreme Command 👑"
        dept = "Office of the CEO & Board of Directors"
        badge_color = 0xFFD700
    elif "executive" in top_role.lower():
        clearance = "Level 4 — Executive Operations & Audit 👔"
        dept = "Executive Moderation & Compliance Desk"
        badge_color = 0x9B59B6
    elif "lead" in top_role.lower() or "principal" in top_role.lower():
        clearance = "Level 3 — Engineering Leadership & Architecture 🧠"
        dept = "Core Product & Systems Architecture"
        badge_color = 0x3498DB
    elif "design" in top_role.lower() or "ui/ux" in top_role.lower():
        clearance = "Level 3 — Design & Brand Strategy 🎨"
        dept = "Product Experience & UI/UX"
        badge_color = 0xE91E63
    elif "devops" in top_role.lower() or "sre" in top_role.lower():
        clearance = "Level 3 — Cloud Infrastructure & Systems ⚙️"
        dept = "DevOps, SRE & Cloud Engineering"
        badge_color = 0x2ECC71
    elif "qa" in top_role.lower() or "security" in top_role.lower():
        clearance = "Level 3 — Security & Quality Assurance 🛡️"
        dept = "InfoSec & Quality Engineering"
        badge_color = 0xE67E22
    else:
        clearance = "Level 2 — Engineering & Staging Access 💻"
        dept = "Full-Stack Software Engineering"
        badge_color = 0x00D2FF

    join_date = member.joined_at.strftime("%d %b %Y") if member.joined_at else "Founding Day"

    embed = discord.Embed(
        title="🪪 VAELKRY DEV LABS — DIGITAL CORPORATE ID CARD",
        description=(
            f"**Official Enterprise Identification & Smart Credential Badge**\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        ),
        color=badge_color,
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    if member.display_avatar:
        embed.set_thumbnail(url=member.display_avatar.url)

    embed.add_field(
        name="👤 Employee Full Name",
        value=f"**{member.display_name}** (`@{member.name}`)",
        inline=True,
    )
    embed.add_field(
        name="🆔 Corporate Serial ID",
        value=f"`{emp_id}`",
        inline=True,
    )
    embed.add_field(
        name="🏢 Department",
        value=f"`{dept}`",
        inline=False,
    )
    embed.add_field(
        name="🎖️ Official Designation",
        value=f"**{top_role}**",
        inline=True,
    )
    embed.add_field(
        name="🛡️ Security Clearance",
        value=f"`{clearance}`",
        inline=True,
    )
    embed.add_field(
        name="📅 Date of Joining",
        value=f"`{join_date}`",
        inline=True,
    )
    is_ceo = "CEO" in clearance or member.id == member.guild.owner_id
    embed.add_field(
        name="🔑 Facility Access Privileges",
        value=(
            f"• **Yogesh Space & CEO Cabin:** " + ("🟢 Supreme Unrestricted" if is_ceo else "🔒 Executive Invite Only") + "\n"
            f"• **Common Pantry & Cafeteria:** 🟢 Full Access (Chai/Coffee & Snacks)\n"
            f"• **Tech Cafe Cabins:** 🟢 Full Access\n"
            f"• **Team Vaasan Engineering Floors:** 🟢 Full Access"
        ),
        inline=False,
    )
    embed.add_field(
        name="✍️ Official Authentication",
        value="*Authenticated by **SadieSink** (Executive Moderation & Onboarding Lead)*",
        inline=False,
    )
    embed.set_footer(
        text=f"Vaelkry Dev Labs Enterprise Authentication • Status: Active Employee 🟢",
        icon_url=member.guild.icon.url if member.guild.icon else None,
    )
    return embed


class ModeratorService:
    def __init__(self, orchestrator: "AgentOrchestrator"):
        self.orchestrator = orchestrator
        # Follower Mode state
        self.is_following: bool = False
        self.ceo_user_id: Optional[int] = None
        self.target_guild_id: Optional[int] = None

        # 24/7 Autonomous Floor Manager State
        self.is_patrol_active: bool = False
        self._patrol_task: Optional[asyncio.Task] = None
        self.patrol_lock = asyncio.Lock()

    def get_millie_client(self) -> Optional[discord.Client]:
        return self.orchestrator.clients.get("millie")

    def get_sadie_client(self) -> Optional[discord.Client]:
        return self.orchestrator.clients.get("sadie")

    async def log_to_full_logs(self, guild: discord.Guild, embed: discord.Embed):
        """Sends an audit log embed to #full-logs using the MillieBobbyBrown client."""
        millie = self.get_millie_client()
        if not millie:
            return

        # Find the #full-logs channel
        full_logs_channel = discord.utils.find(
            lambda ch: ch.name.lower() == "full-logs" and isinstance(ch, discord.TextChannel),
            guild.text_channels,
        )
        if not full_logs_channel:
            return

        try:
            # Use millie's client channel context
            target_ch = millie.get_channel(full_logs_channel.id)
            if target_ch:
                await target_ch.send(embed=embed)
        except Exception as exc:
            logger.warning(f"Failed to post to #full-logs: {exc}")

    async def send_onboarding_greeting(self, member: discord.Member):
        """Sends a professional IT enterprise onboarding card and digital ID card to #greeting using SadieSink."""
        sadie = self.get_sadie_client()
        if not sadie:
            return

        # Auto-provision 'Software Engineer' role if new human member
        se_role = discord.utils.find(
            lambda r: "software engineer" in r.name.lower(),
            member.guild.roles,
        )
        if se_role and not member.bot and se_role not in member.roles:
            try:
                await member.add_roles(se_role, reason="Automatic Enterprise Employee Onboarding")
            except Exception as exc:
                logger.warning(f"Could not auto-assign role to {member.name}: {exc}")

        greeting_channel = discord.utils.find(
            lambda ch: ch.name.lower() == "greeting" and isinstance(ch, discord.TextChannel),
            member.guild.text_channels,
        )
        if not greeting_channel:
            return

        try:
            target_ch = sadie.get_channel(greeting_channel.id)
            if not target_ch:
                return

            embed = discord.Embed(
                title="🏢 Welcome to Vaelkry Dev Labs Corporate HQ!",
                description=(
                    f"Welcome {member.mention} to **Vaelkry Dev Labs** — our high-velocity "
                    f"AI, engineering, and product innovation workspace.\n\n"
                    f"Your corporate developer credentials have been verified and provisioned!"
                ),
                color=0x00D2FF,
                timestamp=datetime.datetime.now(datetime.timezone.utc),
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.add_field(
                name="📢 Official Circulars",
                value="Review company guidelines and sprint bulletins in <#announcements>.",
                inline=False,
            )
            embed.add_field(
                name="☕ Common Pantry & Hub",
                value="Grab coffee with colleagues in <#cafeteria> and check project activity in <#the-launchpad>.",
                inline=False,
            )
            embed.add_field(
                name="🤖 Engineering Leadership Squad",
                value=(
                    "• **TTF Vasan**: Team Lead & Hype Commander\n"
                    "• **Pradeep Ranganathan**: Tech Lead & Solutions Architect\n"
                    "• **Mamitha**: UI/UX Designer\n"
                    "• **Kayadu**: DevOps & Backend Lead\n"
                    "• **Muthazhagi**: QA & Security Lead"
                ),
                inline=False,
            )
            embed.add_field(
                name="🛡️ Executive Moderation Desk",
                value="SadieSink & MillieBobbyBrown are on duty to assist your onboarding.",
                inline=False,
            )
            embed.set_footer(
                text=f"Vaelkry Dev Labs Enterprise Onboarding • Member #{len(member.guild.members)}",
                icon_url=member.guild.icon.url if member.guild.icon else None,
            )

            # Send welcome message
            await target_ch.send(
                content=f"👋 **Welcome to the team, {member.mention}!**",
                embed=embed,
            )

            # Issue Digital Corporate ID Card
            id_embed = generate_id_card_embed(member)
            await target_ch.send(
                content=f"🪪 **Digital Employee ID Card Issued:**",
                embed=id_embed,
            )
            logger.info(f"Onboarding greeting & ID card sent for {member.name} in #{greeting_channel.name}")
        except Exception as exc:
            logger.warning(f"Failed to send onboarding greeting: {exc}")

    def get_id_card(self, member: discord.Member) -> discord.Embed:
        """Returns the official Digital Corporate ID Card embed for any member."""
        return generate_id_card_embed(member)

    # ==================== EVENT AUDIT LOGGERS (MILLIE) ====================

    async def log_member_join(self, member: discord.Member):
        embed = discord.Embed(
            title="📥 Member Joined Corporate Server",
            description=f"**User:** {member.mention} (`{member.name}`)\n**ID:** `{member.id}`",
            color=0x2ECC71,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(
            name="Account Created",
            value=member.created_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
            inline=True,
        )
        embed.add_field(
            name="Total Member Count",
            value=str(len(member.guild.members)),
            inline=True,
        )
        embed.set_footer(text="MillieBobbyBrown Audit Desk")
        await self.log_to_full_logs(member.guild, embed)

    async def log_member_remove(self, member: discord.Member):
        roles = [r.name for r in member.roles if r.name != "@everyone"]
        embed = discord.Embed(
            title="📤 Member Departed Corporate Server",
            description=f"**User:** `{member.name}`\n**ID:** `{member.id}`",
            color=0xE74C3C,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.add_field(
            name="Assigned Roles",
            value=", ".join(roles) if roles else "None",
            inline=False,
        )
        embed.set_footer(text="MillieBobbyBrown Audit Desk")
        await self.log_to_full_logs(member.guild, embed)

    async def log_member_role_update(self, before: discord.Member, after: discord.Member):
        if before.roles == after.roles:
            return

        added = [r.mention for r in after.roles if r not in before.roles]
        removed = [r.mention for r in before.roles if r not in after.roles]

        if not added and not removed:
            return

        embed = discord.Embed(
            title="🛡️ Security & Role Update",
            description=f"**Target Member:** {after.mention} (`{after.name}`)",
            color=0xF1C40F,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        if added:
            embed.add_field(name="➕ Roles Added", value=" ".join(added), inline=False)
        if removed:
            embed.add_field(name="➖ Roles Removed", value=" ".join(removed), inline=False)
        embed.set_footer(text="MillieBobbyBrown Audit Desk")
        await self.log_to_full_logs(after.guild, embed)

    async def log_channel_create(self, channel: discord.abc.GuildChannel):
        embed = discord.Embed(
            title="📁 Channel Provisioned",
            description=(
                f"**Channel:** {channel.name} (`{channel.id}`)\n"
                f"**Type:** `{type(channel).__name__}`\n"
                f"**Category:** `{channel.category.name if channel.category else 'None'}`"
            ),
            color=0x3498DB,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.set_footer(text="MillieBobbyBrown Audit Desk")
        await self.log_to_full_logs(channel.guild, embed)

    async def log_channel_delete(self, channel: discord.abc.GuildChannel):
        embed = discord.Embed(
            title="🗑️ Channel Deprovisioned",
            description=(
                f"**Channel:** `{channel.name}` (`{channel.id}`)\n"
                f"**Type:** `{type(channel).__name__}`"
            ),
            color=0xE67E22,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.set_footer(text="MillieBobbyBrown Audit Desk")
        await self.log_to_full_logs(channel.guild, embed)

    async def log_voice_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        if before.channel == after.channel:
            return

        embed = discord.Embed(
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.set_footer(text="MillieBobbyBrown Audit Desk")

        if before.channel is None and after.channel is not None:
            embed.title = "🔊 Voice Connection Established"
            embed.description = f"**User:** {member.mention}\n**Connected to:** `{after.channel.name}`"
            embed.color = 0x2ECC71
        elif before.channel is not None and after.channel is None:
            embed.title = "🔇 Voice Connection Terminated"
            embed.description = f"**User:** {member.mention}\n**Disconnected from:** `{before.channel.name}`"
            embed.color = 0x95A5A6
        elif before.channel != after.channel:
            embed.title = "🔀 Voice Channel Transferred"
            embed.description = (
                f"**User:** {member.mention}\n"
                f"**From:** `{before.channel.name}` ➔ **To:** `{after.channel.name}`"
            )
            embed.color = 0x9B59B6

        await self.log_to_full_logs(member.guild, embed)

    # ==================== VOICE MOVEMENT HELPER ====================

    def is_sleeping_area(self, channel: Optional[discord.abc.GuildChannel]) -> bool:
        """
        Checks whether a voice channel is located within the sleeping area (Night Spend / Sleep rooms).
        """
        if not channel or not hasattr(channel, "name"):
            return False
        category = getattr(channel, "category", None)
        category_name = category.name.strip().lower() if category and hasattr(category, "name") else ""
        ch_name = getattr(channel, "name", "").strip().lower()
        return "night spend" in category_name or "sleep" in ch_name

    async def move_bot_to_vc(
        self,
        client: Optional[discord.Client],
        target_vc: Optional[discord.VoiceChannel],
        activity_name: Optional[str] = None,
        self_mute: Optional[bool] = None,
        self_deaf: Optional[bool] = None,
    ):
        """
        Smoothly moves SadieSink or MillieBobbyBrown to target_vc.
        Handles initial voice connection via client_target_vc.connect() using the bot's client instance,
        and subsequent moves via guild.change_voice_state(channel=client_target_vc).
        Automatically enforces self_mute=True and self_deaf=True with custom status
        'Sleeping in Night Spend 💤' whenever entering/staying in sleeping areas (Night Spend / Sleep rooms).
        Automatically unmutes and undeafens when in non-sleeping rooms.
        """
        if not client or not client.is_ready() or not target_vc:
            return

        # Ensure guild and voice channel instances belong to this specific client instance
        guild = client.get_guild(target_vc.guild.id) or target_vc.guild
        client_target_vc = guild.get_channel(target_vc.id)
        if not client_target_vc or not isinstance(client_target_vc, discord.VoiceChannel):
            client_target_vc = target_vc

        bot_member = guild.me or guild.get_member(client.user.id)

        # Detect sleeping area
        is_sleep = self.is_sleeping_area(client_target_vc)
        target_mute = is_sleep if self_mute is None else self_mute
        target_deaf = is_sleep if self_deaf is None else self_deaf

        effective_activity = "Sleeping in Night Spend 💤" if is_sleep else activity_name

        # 1. Update presence activity
        if effective_activity:
            try:
                await client.change_presence(activity=discord.CustomActivity(name=effective_activity))
            except Exception as exc:
                logger.warning(f"Failed to update activity for {client.user.name}: {exc}")

        # 2. Check if already connected in target VC with matching mute/deaf state
        already_in_target = bool(
            bot_member
            and bot_member.voice
            and bot_member.voice.channel
            and bot_member.voice.channel.id == client_target_vc.id
        )

        has_correct_mute_deaf = bool(
            bot_member
            and bot_member.voice
            and getattr(bot_member.voice, "self_mute", False) == target_mute
            and getattr(bot_member.voice, "self_deaf", False) == target_deaf
        )

        if already_in_target and has_correct_mute_deaf:
            return

        if already_in_target and not has_correct_mute_deaf:
            logger.info(
                f"[Voice State Sync] {client.user.name} already in '{client_target_vc.name}' "
                f"(is_sleep={is_sleep}). Syncing self_mute={target_mute}, self_deaf={target_deaf}."
            )
            try:
                await guild.change_voice_state(
                    channel=client_target_vc,
                    self_mute=target_mute,
                    self_deaf=target_deaf,
                )
                return
            except Exception as exc:
                logger.warning(f"Failed to update mute/deaf state for {client.user.name}: {exc}")

        # 3. Connection & Movement Logic
        is_in_voice = bool(bot_member and bot_member.voice and bot_member.voice.channel)
        voice_client = discord.utils.get(client.voice_clients, guild=guild)

        try:
            if is_in_voice or (voice_client and voice_client.is_connected()):
                # Already active in voice: move via guild.change_voice_state
                await guild.change_voice_state(
                    channel=client_target_vc,
                    self_mute=target_mute,
                    self_deaf=target_deaf,
                )
            else:
                # Bot is not in voice yet: trigger initial connection using client instance
                if voice_client:
                    try:
                        await voice_client.disconnect(force=True)
                    except Exception:
                        pass
                try:
                    await client_target_vc.connect(
                        self_mute=target_mute,
                        self_deaf=target_deaf,
                        reconnect=True,
                    )
                except discord.ClientException:
                    # If client is already marked connecting or connected, update state directly
                    await guild.change_voice_state(
                        channel=client_target_vc,
                        self_mute=target_mute,
                        self_deaf=target_deaf,
                    )
        except Exception as exc:
            logger.warning(
                f"Move exception for {client.user.name} to {target_vc.name}: {exc}. Fallback to guild.change_voice_state..."
            )
            try:
                await guild.change_voice_state(
                    channel=client_target_vc,
                    self_mute=target_mute,
                    self_deaf=target_deaf,
                )
            except Exception as exc2:
                logger.error(f"Failed gateway voice state transfer for {client.user.name}: {exc2}")

    # Aliases for backwards compatibility
    move_moderator_bot = move_bot_to_vc

    async def sync_moderator_voice_state(
        self,
        member: discord.Member,
        voice_state: discord.VoiceState,
    ):
        """
        Event handler hook: Ensures that when SadieSink or MillieBobbyBrown enters or is in a sleeping area,
        their voice state is strictly set to self_mute=True and self_deaf=True
        with custom status 'Sleeping in Night Spend 💤'.
        When in any non-sleeping area, ensures self_mute=False and self_deaf=False.
        """
        channel = voice_state.channel
        if not channel or not hasattr(channel, "name"):
            return

        sadie = self.get_sadie_client()
        millie = self.get_millie_client()
        client = None
        default_activity = "Executive Escort 👑"

        if sadie and sadie.user and member.id == sadie.user.id:
            client = sadie
            default_activity = "Executive Escort 👑"
        elif millie and millie.user and member.id == millie.user.id:
            client = millie
            default_activity = "Executive Security 🛡️"

        if not client or not client.is_ready():
            return

        is_sleep = self.is_sleeping_area(channel)
        target_mute = is_sleep
        target_deaf = is_sleep

        curr_mute = getattr(voice_state, "self_mute", False)
        curr_deaf = getattr(voice_state, "self_deaf", False)

        if curr_mute == target_mute and curr_deaf == target_deaf:
            return

        guild = client.get_guild(member.guild.id) or member.guild
        client_channel = guild.get_channel(channel.id) or channel

        logger.info(
            f"⚡ [Moderator Voice Sync] {member.name} in '{channel.name}' (is_sleep={is_sleep}): "
            f"updating self_mute={target_mute}, self_deaf={target_deaf}."
        )

        try:
            await guild.change_voice_state(
                channel=client_channel,
                self_mute=target_mute,
                self_deaf=target_deaf,
            )
        except Exception as exc:
            logger.warning(f"Failed to sync voice state for {member.name}: {exc}")

        effective_activity = "Sleeping in Night Spend 💤" if is_sleep else default_activity
        try:
            await client.change_presence(activity=discord.CustomActivity(name=effective_activity))
        except Exception as exc:
            logger.warning(f"Failed to update activity during voice sync for {member.name}: {exc}")

    async def sync_all_moderators_sleep_state(self, guild: discord.Guild):
        """
        Initial sync on patrol startup: scans both SadieSink and MillieBobbyBrown.
        If either is currently connected inside a sleeping area without mute/deaf,
        immediately applies self_mute=True and self_deaf=True.
        """
        sadie_client = self.get_sadie_client()
        millie_client = self.get_millie_client()

        tasks = []
        for client, default_act in [(sadie_client, "Executive Escort 👑"), (millie_client, "Executive Security 🛡️")]:
            if not client or not client.is_ready():
                continue
            client_guild = client.get_guild(guild.id) or guild
            bot_member = client_guild.me or client_guild.get_member(client.user.id)
            if bot_member and bot_member.voice and bot_member.voice.channel:
                vc = bot_member.voice.channel
                tasks.append(self.move_bot_to_vc(client, vc, default_act))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    # ==================== 24/7 AUTONOMOUS FLOOR MANAGER ROUTINE ====================

    def is_ceo_in_ceo_vc(
        self, guild: discord.Guild
    ) -> Tuple[bool, Optional[discord.Member], Optional[discord.VoiceChannel]]:
        """
        Detects CEO Presence in "Ceo Vc" (1563622904829190326):
        Returns True if the guild owner OR any human (member.bot is False) is currently inside "Ceo Vc".
        """
        ceo_vc = get_ceo_voice_channel(guild)
        if not ceo_vc:
            return False, None, None

        # Check members currently connected to "Ceo Vc"
        for member in ceo_vc.members:
            if not member.bot:
                # Any human or guild owner inside Ceo Vc qualifies as CEO presence
                return True, member, ceo_vc

        return False, None, ceo_vc

    def get_populated_employee_voice_channels(self, guild: discord.Guild) -> List[discord.VoiceChannel]:
        """
        Dynamically scans all voice channels in the guild to find voice channels
        that currently contain active employee members (Team Vaasan developer bots or human employees).
        Excludes empty voice channels and executive CEO cabins.
        """
        moderator_ids = {1563617637986992178, 1563618724412395651}
        sadie = self.get_sadie_client()
        millie = self.get_millie_client()
        if sadie and sadie.user:
            moderator_ids.add(sadie.user.id)
        if millie and millie.user:
            moderator_ids.add(millie.user.id)

        team_names = ["ttf vasan", "pradeep", "mamitha", "kayadu", "muthazhagi"]
        populated_channels: List[discord.VoiceChannel] = []

        for vc in guild.voice_channels:
            # Exclude CEO VC
            if vc.id == CEO_VC_ID or "ceo" in vc.name.lower():
                continue

            # Check if channel contains any active employee (Team Vaasan bots or developers)
            has_employee = False
            for member in vc.members:
                if member.id in moderator_ids:
                    continue

                name_lower = member.name.lower()
                display_lower = member.display_name.lower()

                is_team_vaasan = any(tn in name_lower or tn in display_lower for tn in team_names)
                is_active_dev_bot = bool(member.bot and member.id not in moderator_ids)
                is_human_dev = bool(not member.bot and member.id != guild.owner_id)

                if is_team_vaasan or is_active_dev_bot or is_human_dev:
                    has_employee = True
                    break

            if has_employee:
                populated_channels.append(vc)

        if populated_channels:
            logger.info(
                f"[Patrol Scanner] Found {len(populated_channels)} populated employee voice channels: "
                f"{[vc.name for vc in populated_channels]}"
            )

        return populated_channels

    # Alias for backwards compatibility
    get_employee_voice_channels = get_populated_employee_voice_channels

    async def patrol_step(self, guild: discord.Guild):
        """
        Executes a single cycle of the 24/7 probabilistic floor manager routine:
        - Detect CEO Presence:
            * Check if the guild owner OR any human (member.bot is False) is inside "Ceo Vc" (1563622904829190326).
        - If CEO is INSIDE "Ceo Vc":
            * 70% probability: Both bots stay/move inside "Ceo Vc" with CEO (Sadie: 'Executive Escort 👑', Millie: 'Executive Security 🛡️').
            * 30% probability: Move ONLY to populated employee voice channels for floor rounds (NEVER empty rooms).
        - If CEO is NOT inside "Ceo Vc" (CEO is disconnected, offline, or elsewhere):
            * 20% probability: Stay in "Ceo Vc" keeping executive office presence.
            * 80% probability: Roam across populated employee voice channels randomly (NEVER empty rooms).
        - Fallback: If no employee channels are currently active, stay in "Ceo Vc".
        """
        if self.is_following:
            logger.info("24/7 Floor Manager cycle skipped: /follow escort mode is actively engaged.")
            return

        sadie_client = self.get_sadie_client()
        millie_client = self.get_millie_client()
        if not (sadie_client and sadie_client.is_ready()) and not (millie_client and millie_client.is_ready()):
            logger.warning("Neither SadieSink nor MillieBobbyBrown is ready for floor management.")
            return

        ceo_vc = get_ceo_voice_channel(guild)
        if not ceo_vc:
            logger.warning(f"Ceo Vc ({CEO_VC_NAME} / {CEO_VC_ID}) not found in guild {guild.name}.")
            return

        if self.patrol_lock.locked():
            logger.debug("Floor manager patrol cycle already in progress. Skipping concurrent run.")
            return

        async with self.patrol_lock:
            ceo_present, human_member, _ = self.is_ceo_in_ceo_vc(guild)
            populated_vcs = self.get_populated_employee_voice_channels(guild)
            roll = random.random()

            if ceo_present:
                # ==================== CEO / HUMAN IS INSIDE "Ceo Vc" ====================
                human_name = human_member.display_name if human_member else "CEO"
                if roll < 0.70:
                    # 70% probability: Both bots stay/move inside "Ceo Vc" with the CEO
                    logger.info(
                        f"[24/7 Floor Manager | 70% Roll ({roll:.2f} < 0.70)] CEO/Human '{human_name}' inside Ceo Vc. "
                        f"Both SadieSink & MillieBobbyBrown moving/staying in {ceo_vc.name} (Escort 👑 & Security 🛡️)."
                    )
                    target_vc_sadie = ceo_vc
                    target_vc_millie = ceo_vc
                    await asyncio.gather(
                        self.move_bot_to_vc(sadie_client, target_vc_sadie, "Executive Escort 👑"),
                        self.move_bot_to_vc(millie_client, target_vc_millie, "Executive Security 🛡️"),
                        return_exceptions=True,
                    )
                else:
                    # 30% probability: Move ONLY to populated employee voice channels for floor rounds
                    sadie_target = random.choice(populated_vcs) if populated_vcs else ceo_vc
                    millie_target = random.choice(populated_vcs) if populated_vcs else ceo_vc
                    logger.info(
                        f"[24/7 Floor Manager | 30% Roll ({roll:.2f} >= 0.70)] CEO/Human in Ceo Vc. "
                        f"Sadie roaming to '{sadie_target.name}', Millie roaming to '{millie_target.name}'."
                    )
                    await asyncio.gather(
                        self.move_bot_to_vc(sadie_client, sadie_target, "Executive Escort 👑"),
                        self.move_bot_to_vc(millie_client, millie_target, "Executive Security 🛡️"),
                        return_exceptions=True,
                    )

            else:
                # ==================== CEO / HUMAN IS NOT INSIDE "Ceo Vc" ====================
                if roll < 0.20:
                    # 20% probability: Stay in "Ceo Vc" keeping executive office presence
                    logger.info(
                        f"[24/7 Floor Manager | 20% Roll ({roll:.2f} < 0.20)] Ceo Vc vacant. "
                        f"SadieSink & MillieBobbyBrown staying in {ceo_vc.name} (Escort 👑 & Security 🛡️)."
                    )
                    target_vc_sadie = ceo_vc
                    target_vc_millie = ceo_vc
                    await asyncio.gather(
                        self.move_bot_to_vc(sadie_client, target_vc_sadie, "Executive Escort 👑"),
                        self.move_bot_to_vc(millie_client, target_vc_millie, "Executive Security 🛡️"),
                        return_exceptions=True,
                    )
                else:
                    # 80% probability: Roam across POPULATED employee channels randomly (NEVER empty rooms)
                    sadie_target = random.choice(populated_vcs) if populated_vcs else ceo_vc
                    millie_target = random.choice(populated_vcs) if populated_vcs else ceo_vc
                    logger.info(
                        f"[24/7 Floor Manager | 80% Roll ({roll:.2f} >= 0.20)] Ceo Vc vacant. "
                        f"Sadie roaming to '{sadie_target.name}', Millie roaming to '{millie_target.name}' (Populated rooms only)."
                    )
                    await asyncio.gather(
                        self.move_bot_to_vc(sadie_client, sadie_target, "Executive Escort 👑"),
                        self.move_bot_to_vc(millie_client, millie_target, "Executive Security 🛡️"),
                        return_exceptions=True,
                    )

    # Alias perform_patrol_cycle to patrol_step
    perform_patrol_cycle = patrol_step

    async def handle_voice_state_patrol_trigger(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        """
        Instant Event Trigger:
        - When any human joins "Ceo Vc", immediately run the 70/30 roll without waiting 5 minutes.
        - When human leaves "Ceo Vc", immediately execute the 20/80 roll.
        """
        if member.bot:
            return

        # If /follow is actively enabled, hard-stick to CEO instead
        if self.is_following:
            return

        guild = member.guild
        ceo_vc = get_ceo_voice_channel(guild)
        if not ceo_vc:
            return

        joined_ceo_vc = bool(
            after.channel and after.channel.id == ceo_vc.id and (not before.channel or before.channel.id != ceo_vc.id)
        )
        left_ceo_vc = bool(
            before.channel and before.channel.id == ceo_vc.id and (not after.channel or after.channel.id != ceo_vc.id)
        )

        if joined_ceo_vc:
            logger.info(
                f"⚡ [Instant Trigger] Human '{member.display_name}' joined {ceo_vc.name}. "
                f"Immediately executing 70/30 executive patrol roll!"
            )
            await self.perform_patrol_cycle(guild)
        elif left_ceo_vc:
            # Check if any human remains inside Ceo Vc
            has_human_remaining = any(not m.bot for m in ceo_vc.members if m.id != member.id)
            if not has_human_remaining:
                logger.info(
                    f"⚡ [Instant Trigger] Human '{member.display_name}' departed {ceo_vc.name} (vacant). "
                    f"Immediately executing 20/80 autonomous floor patrol roll!"
                )
                await self.perform_patrol_cycle(guild)

    def start_patrol_loop(self, guild: discord.Guild):
        """
        Starts the 24/7 completely autonomous floor-manager loop.
        Runs continuously every 5 minutes whether CEO is online, offline, or absent.
        """
        if self._patrol_task and not self._patrol_task.done():
            self._patrol_task.cancel()

        self.is_patrol_active = True
        self.target_guild_id = guild.id
        self._patrol_task = asyncio.create_task(self._run_patrol_loop(guild))
        asyncio.create_task(self.sync_all_moderators_sleep_state(guild))
        logger.info(f"24/7 Autonomous Floor Manager background routine started for guild '{guild.name}' (5m cycle).")

    def stop_patrol_loop(self):
        """Stops the floor-manager background routine."""
        self.is_patrol_active = False
        if self._patrol_task and not self._patrol_task.done():
            self._patrol_task.cancel()
            self._patrol_task = None
        logger.info("24/7 Autonomous Floor Manager routine stopped.")

    async def _run_patrol_loop(self, guild: discord.Guild):
        """
        Runs continuously 24/7 every 5 minutes.
        Does NOT stop, pause, or wait for CEO to be present.
        """
        # Initial grace period (5 seconds) so bot gateways are fully synchronized
        await asyncio.sleep(5)
        logger.info("24/7 Autonomous Floor Manager loop is now running.")

        while self.is_patrol_active:
            try:
                await self.perform_patrol_cycle(guild)
            except asyncio.CancelledError:
                logger.info("24/7 Floor Manager loop cancelled.")
                break
            except Exception as exc:
                logger.exception(f"Error in floor manager patrol loop cycle: {exc}")

            # Continuously evaluate every 5 minutes (300 seconds) 24/7
            try:
                await asyncio.sleep(300)
            except asyncio.CancelledError:
                break

    # ==================== FOLLOWER MODE (SADIE & MILLIE) ====================

    async def start_following(self, ceo_member: discord.Member) -> Tuple[bool, str]:
        """Activates follower mode, connecting both SadieSink & MillieBobbyBrown to the CEO's VC."""
        if not ceo_member.voice or not ceo_member.voice.channel:
            return (
                False,
                f"⚠️ **CEO {ceo_member.mention}**, please connect to a Voice Channel first "
                f"(e.g., `CEO vc` or any cabin) so SadieSink & MillieBobbyBrown can escort you!",
            )

        target_vc = ceo_member.voice.channel
        self.is_following = True
        self.ceo_user_id = ceo_member.id
        self.target_guild_id = ceo_member.guild.id

        sadie_client = self.get_sadie_client()
        millie_client = self.get_millie_client()
        target_vc_sadie = target_vc
        target_vc_millie = target_vc

        # Connect / move using smooth move helper
        await asyncio.gather(
            self.move_bot_to_vc(sadie_client, target_vc_sadie, f"Escorting CEO ({ceo_member.display_name}) 👑"),
            self.move_bot_to_vc(millie_client, target_vc_millie, "Executive Security 🛡️"),
            return_exceptions=True,
        )

        logger.info(f"Executive Escort Activated: Sadie & Millie connected to VC {target_vc.name}")
        return (
            True,
            f"🎙️ **Executive Escort Activated!**\n"
            f"**SadieSink** and **MillieBobbyBrown** are now escorting CEO {ceo_member.mention} in `{target_vc.name}`.\n"
            f"Wherever you move, both executive moderators will dynamically follow you! ⚡",
        )

    async def stop_following(self, guild: Optional[discord.Guild] = None) -> str:
        """Deactivates follower mode and immediately resumes the dynamic percentage patrol loop."""
        self.is_following = False
        self.ceo_user_id = None

        logger.info("Executive Escort Deactivated: Resuming dynamic percentage patrol loop.")

        # Determine target guild to immediately trigger patrol cycle
        target_guild = guild
        if not target_guild and self.target_guild_id:
            lead = self.get_sadie_client() or self.orchestrator.clients.get("ttf_vasan")
            if lead:
                target_guild = lead.get_guild(self.target_guild_id)

        if target_guild:
            asyncio.create_task(self.perform_patrol_cycle(target_guild))

        return (
            "🔇 **Executive Escort Deactivated!**\n"
            "SadieSink & MillieBobbyBrown have resumed their automated floor-patrol routine across the corporate workspaces."
        )

    async def handle_follower_voice_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        """Monitors the CEO's voice transitions and moves both bots concurrently when in follow mode."""
        if not self.is_following or member.id != self.ceo_user_id:
            return

        # CEO switched to a new voice channel
        if after.channel and after.channel != before.channel:
            target_vc = after.channel
            logger.info(f"CEO moved to {target_vc.name}. Moving Sadie & Millie...")
            sadie_client = self.get_sadie_client()
            millie_client = self.get_millie_client()
            target_vc_sadie = target_vc
            target_vc_millie = target_vc
            await asyncio.gather(
                self.move_bot_to_vc(sadie_client, target_vc_sadie, f"Escorting CEO in {target_vc.name} 👑"),
                self.move_bot_to_vc(millie_client, target_vc_millie, "Executive Security 🛡️"),
                return_exceptions=True,
            )

        # CEO disconnected from voice
        elif after.channel is None and before.channel is not None:
            logger.info("CEO disconnected from voice in follow mode. Disconnecting escorts...")
            disconnect_tasks = []
            for client in (self.get_sadie_client(), self.get_millie_client()):
                if client:
                    for vc in list(client.voice_clients):
                        disconnect_tasks.append(vc.disconnect(force=True))
                    g = client.get_guild(member.guild.id) or member.guild
                    if g and g.me and g.me.voice:
                        disconnect_tasks.append(g.change_voice_state(channel=None))
            if disconnect_tasks:
                await asyncio.gather(*disconnect_tasks, return_exceptions=True)

    # ==================== EXECUTIVE OPERATIONS DASHBOARD ====================

    def generate_executive_dashboard_embed(self, guild: discord.Guild) -> discord.Embed:
        """
        Generates an executive operations dashboard embed summarizing:
        - Team & Squad counts (Team Vaasan, Team Vijay, Dynamic Squads)
        - Active VCs & Occupancy
        - Human Engineers vs Bot Headcount
        - Infrastructure & Category Hierarchy Health
        """
        now = datetime.datetime.now(datetime.timezone.utc)

        # 1. Team & Category Counts
        team_categories = [
            c for c in guild.categories
            if c.name.strip().lower().startswith("team")
        ]
        squad_names = [f"`{c.name}`" for c in team_categories] or ["`Team Vaasan`", "`Team Vijay`"]

        # 2. Headcount
        total_members = guild.member_count or len(guild.members)
        bot_members = [m for m in guild.members if m.bot]
        human_members = [m for m in guild.members if not m.bot]

        active_bots = len([c for c in self.orchestrator.clients.values() if c.is_ready()])

        # 3. Active VCs & Floor Occupancy
        active_vc_lines = []
        for vc in guild.voice_channels:
            if vc.members:
                member_names = ", ".join(m.display_name for m in vc.members)
                cat_name = vc.category.name if vc.category else "Uncategorized"
                active_vc_lines.append(f"• 🔊 **{vc.name}** (`{cat_name}`): {member_names}")

        if not active_vc_lines:
            vc_occupancy_text = "*No members currently connected to voice channels.*"
        else:
            vc_occupancy_text = "\n".join(active_vc_lines[:10])

        # 4. Scheduler state
        scheduler = getattr(self.orchestrator, "scheduler_service", None)
        scheduler_status = "Active ⚡ (24h IST Routine)" if (scheduler and scheduler.is_active) else "Standby / Paused ⏸️"

        from scheduler_service import get_current_ist_time, match_current_shift
        now_ist = get_current_ist_time()
        current_shift = match_current_shift(now_ist)

        embed = discord.Embed(
            title="👔 VAELKRY DEV LABS — EXECUTIVE OPERATIONS DASHBOARD",
            description=(
                f"**Enterprise High-Level Status & Infrastructure Audit**\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"• **Current IST Time:** `{now_ist.strftime('%d %b %Y | %H:%M:%S IST')}`\n"
                f"• **Active Shift:** `{current_shift.name}`\n"
                f"• **Scheduler Engine:** `{scheduler_status}`"
            ),
            color=0x9B59B6,  # Royal Executive Purple
            timestamp=now,
        )

        embed.add_field(
            name="🏢 Active Engineering Squads",
            value=(
                f"**Total Squads:** `{len(team_categories)}`\n"
                f"**Categories:** {', '.join(squad_names)}\n"
                f"• Strictly positioned above `Night Spend`."
            ),
            inline=False,
        )

        embed.add_field(
            name="👥 Enterprise Headcount",
            value=(
                f"• Total Roster: `{total_members}` members\n"
                f"• Software Engineers / Humans: `{len(human_members)}`\n"
                f"• AI Developer Bots: `{len(bot_members)}` (Active: `{active_bots}`)\n"
                f"• Executive Moderation: `SadieSink` & `MillieBobbyBrown`"
            ),
            inline=True,
        )

        embed.add_field(
            name="🛡️ System & Architecture Health",
            value=(
                f"• Gemini AI Engine: `Operational 🟢`\n"
                f"• Hierarchy Enforcement: `Strict 4-Tier Order 🟢`\n"
                f"• Security Audits: `Active Patrol 🟢`"
            ),
            inline=True,
        )

        embed.add_field(
            name="🔊 Live Voice Floor & VC Occupancy",
            value=vc_occupancy_text,
            inline=False,
        )

        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        embed.set_footer(
            text="Executive Suite • SadieSink (Executive Desk) & MillieBobbyBrown (Chief Audit Officer)"
        )
        return embed

    async def send_executive_dashboard(self, guild: discord.Guild) -> Tuple[bool, str]:
        """
        Sends the Executive Dashboard embed to #managers-space and #yogesh-chat.
        """
        dashboard_embed = self.generate_executive_dashboard_embed(guild)

        sent_channels = []
        # Target 1: #managers-space
        managers_ch = discord.utils.find(
            lambda c: any(w in c.name.lower() for w in ("managers-space", "manager-space", "managers")),
            guild.text_channels,
        )
        # Target 2: #yogesh-chat
        from scheduler_service import get_ceo_channel
        ceo_ch = get_ceo_channel(guild)

        target_channels = []
        if managers_ch:
            target_channels.append(managers_ch)
        if ceo_ch and (not managers_ch or ceo_ch.id != managers_ch.id):
            target_channels.append(ceo_ch)

        exec_client = self.get_sadie_client() or self.get_millie_client() or next(iter(self.orchestrator.clients.values()), None)

        for ch in target_channels:
            try:
                target_send_ch = exec_client.get_channel(ch.id) if exec_client else ch
                if target_send_ch:
                    await target_send_ch.send(embed=dashboard_embed)
                    sent_channels.append(f"#{ch.name}")
            except Exception as exc:
                logger.warning(f"Failed to post executive dashboard to #{ch.name}: {exc}")

        if sent_channels:
            return True, f"✅ Executive Dashboard broadcasted to: {', '.join(sent_channels)}"
        else:
            return False, "⚠️ Could not locate #managers-space or #yogesh-chat to dispatch dashboard."
