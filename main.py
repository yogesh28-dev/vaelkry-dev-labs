"""
Vaelkry Dev Labs - Multi-Agent Enterprise Discord System
Main Entry Point orchestrating 7 concurrent Discord bot clients:
- 5 Developer Agents: TTF Vasan, Pradeep Ranganathan, Mamitha, Kayadu, Muthazhagi
- 2 Executive Moderator Agents: SadieSink, MillieBobbyBrown

Features:
1. CEO Handwritten Blueprint Server Reset & Rebuild (/reset_and_build_server)
2. Dynamic Team Category Scaling (/teamcategory)
3. Company Lifecycle & 24h IST Shift Routine Scheduler (/start & /stop)
4. Event Audit Logging into #full-logs (MillieBobbyBrown)
5. Enterprise Onboarding & Greeting into #greeting (SadieSink)
6. Dynamic Executive Voice Escort (/follow & /unfollow)
7. 5-Agent Tanglish AI Project Tech Sprints (!project)
"""

import asyncio
import logging
import random
import sys
from typing import Dict, List, Optional

import discord
from discord import app_commands

from config import AgentConfig, SystemConfig, load_config
from gemini_service import GeminiService
from agents import AGENT_PROMPTS, build_agent_prompt, CASUAL_PLAYER_CHARACTERS
from server_builder import (
    create_dynamic_team_category,
    ensure_enterprise_roles,
    ensure_team_vijay_category,
    format_blueprint_directory,
    is_admin_or_owner,
    reset_and_build_server,
)
from moderator_service import ModeratorService
from cafeteria_service import CafeteriaService, find_cafeteria_channel
from casual_player_service import CasualPlayerService
from scheduler_service import (
    CEO_NOTIFICATION_CHANNEL_ID,
    CEO_NOTIFICATION_CHANNEL_NAME,
    CompanyScheduler,
    get_ceo_channel,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("VaelkryDevLabs")


class VaelkryBotClient(discord.Client):
    """
    Subclass of discord.Client representing a single agent bot within Vaelkry Dev Labs.
    TTF Vasan hosts the slash command suite synchronized directly to the corporate Guild.
    """

    def __init__(self, agent_config: AgentConfig, orchestrator: "AgentOrchestrator", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.agent_config = agent_config
        self.orchestrator = orchestrator

        # Attach CommandTree to TTF Vasan for corporate slash commands
        if agent_config.key == "ttf_vasan":
            self.tree = app_commands.CommandTree(self)
            self._register_slash_commands()

    def _register_slash_commands(self):
        """Registers all enterprise slash commands onto TTF Vasan's CommandTree."""

        @self.tree.command(
            name="start",
            description="Activates Vaelkry Dev Labs company operations and the 24h IST shift scheduler",
        )
        async def start_slash(interaction: discord.Interaction):
            if not interaction.guild:
                await interaction.response.send_message("⚠️ Run within a corporate server!", ephemeral=True)
                return

            member = interaction.guild.get_member(interaction.user.id) or interaction.user
            if not is_admin_or_owner(member, interaction.guild):
                await interaction.response.send_message(
                    "🛑 **Access Denied:** Only the CEO or Admin can activate company operations!",
                    ephemeral=True,
                )
                return

            await interaction.response.defer()
            msg = await self.orchestrator.scheduler_service.start(interaction.guild)
            await interaction.followup.send(msg)

        @self.tree.command(
            name="stop",
            description="Pauses Vaelkry Dev Labs company operations and disconnects bots from voice",
        )
        async def stop_slash(interaction: discord.Interaction):
            if not interaction.guild:
                await interaction.response.send_message("⚠️ Run within a corporate server!", ephemeral=True)
                return

            member = interaction.guild.get_member(interaction.user.id) or interaction.user
            if not is_admin_or_owner(member, interaction.guild):
                await interaction.response.send_message(
                    "🛑 **Access Denied:** Only the CEO or Admin can pause company operations!",
                    ephemeral=True,
                )
                return

            await interaction.response.defer()
            msg = await self.orchestrator.scheduler_service.stop(interaction.guild)
            await interaction.followup.send(msg)

        @self.tree.command(
            name="status",
            description="Displays and routes TTF Vasan operational status logs strictly to #yogesh-chat",
        )
        async def status_slash(interaction: discord.Interaction):
            if not interaction.guild:
                await interaction.response.send_message("⚠️ Run within a corporate server!", ephemeral=True)
                return

            await interaction.response.defer()
            status_embed = self.orchestrator.scheduler_service.get_status_embed(interaction.guild)
            # Route status log embed strictly to CEO channel (yogesh-chat)
            await self.orchestrator.scheduler_service.notify_ceo_channel(interaction.guild, embed=status_embed)
            ceo_ch = get_ceo_channel(interaction.guild)
            ceo_mention = ceo_ch.mention if ceo_ch else f"#{CEO_NOTIFICATION_CHANNEL_NAME}"
            await interaction.followup.send(
                content=f"📊 **Live TTF Vasan operational status log routed strictly to {ceo_mention}!**",
                embed=status_embed,
            )

        @self.tree.command(
            name="reset_and_build_server",
            description="Deletes all channels and strictly builds the CEO Handwritten Blueprint (Owner only)",
        )
        async def reset_build_slash(interaction: discord.Interaction):
            if not interaction.guild:
                await interaction.response.send_message("⚠️ Run within a corporate server!", ephemeral=True)
                return

            member = interaction.guild.get_member(interaction.user.id) or interaction.user
            if not is_admin_or_owner(member, interaction.guild):
                await interaction.response.send_message(
                    "🛑 **Ayyo nanba!** Only the Server Owner or Admin can execute CEO Blueprint resets!",
                    ephemeral=True,
                )
                return

            await interaction.response.defer()
            await self.orchestrator.execute_blueprint_reset_flow(
                guild=interaction.guild,
                send_fn=interaction.followup.send,
            )

        @self.tree.command(
            name="teamcategory",
            description="Dynamically provisions a new team category duplicating the Team Vaasan template",
        )
        @app_commands.describe(team_name="Name of the new engineering team (e.g. Falcon, Alpha, Cyber)")
        async def teamcategory_slash(interaction: discord.Interaction, team_name: str):
            if not interaction.guild:
                await interaction.response.send_message("⚠️ Run within a corporate server!", ephemeral=True)
                return

            member = interaction.guild.get_member(interaction.user.id) or interaction.user
            if not is_admin_or_owner(member, interaction.guild):
                await interaction.response.send_message(
                    "🛑 **Access Denied:** Only administrators can provision team categories!",
                    ephemeral=True,
                )
                return

            await interaction.response.defer()
            await self.orchestrator.execute_team_category_flow(
                guild=interaction.guild,
                team_name=team_name,
                send_fn=interaction.followup.send,
            )

        @self.tree.command(
            name="follow",
            description="Escort Mode: SadieSink & MillieBobbyBrown connect to CEO voice channel and follow dynamically",
        )
        async def follow_slash(interaction: discord.Interaction):
            if not interaction.guild:
                await interaction.response.send_message("⚠️ Run within a corporate server!", ephemeral=True)
                return

            member = interaction.guild.get_member(interaction.user.id) or interaction.user
            if not is_admin_or_owner(member, interaction.guild):
                await interaction.response.send_message(
                    "🛑 **Access Denied:** Only the CEO or Admin can activate Executive Escort mode!",
                    ephemeral=True,
                )
                return

            await interaction.response.defer()
            success, msg = await self.orchestrator.moderator_service.start_following(member)
            await interaction.followup.send(msg)

        @self.tree.command(
            name="unfollow",
            description="Disengages SadieSink & MillieBobbyBrown from voice following mode and resumes patrol",
        )
        async def unfollow_slash(interaction: discord.Interaction):
            await interaction.response.defer()
            msg = await self.orchestrator.moderator_service.stop_following(interaction.guild)
            await interaction.followup.send(msg)

        @self.tree.command(
            name="idcard",
            description="Displays the official Vaelkry Dev Labs Digital Corporate ID Card for an employee",
        )
        @app_commands.describe(member="Select employee to view their Digital ID Card (defaults to you)")
        async def idcard_slash(interaction: discord.Interaction, member: Optional[discord.Member] = None):
            target = member or (interaction.guild.get_member(interaction.user.id) if interaction.guild else interaction.user)
            await interaction.response.defer()
            id_embed = self.orchestrator.moderator_service.get_id_card(target)
            await interaction.followup.send(embed=id_embed)

        @self.tree.command(
            name="provision_roles",
            description="Provisions and synchronizes all 8 enterprise corporate roles (CEO/Admin only)",
        )
        async def provision_roles_slash(interaction: discord.Interaction):
            if not interaction.guild:
                await interaction.response.send_message("⚠️ Run within a corporate server!", ephemeral=True)
                return

            mem = interaction.guild.get_member(interaction.user.id) or interaction.user
            if not is_admin_or_owner(mem, interaction.guild):
                await interaction.response.send_message(
                    "🛑 **Access Denied:** Only the CEO or Admin can provision enterprise roles!",
                    ephemeral=True,
                )
                return

            await interaction.response.defer()
            roles_map = await ensure_enterprise_roles(interaction.guild, self.orchestrator.clients)
            role_names = ", ".join(f"`{r}`" for r in roles_map.keys())
            await interaction.followup.send(
                f"✅ **Enterprise Roles Provisioned & Synchronized!**\n"
                f"Configured roles:\n{role_names}\n"
                f"All bots, CEO, and human software engineers have been provisioned."
            )

        @self.tree.command(
            name="coffee",
            description="Launches a fun 5-agent Tanglish coffee/chai break banter in #cafeteria",
        )
        async def coffee_slash(interaction: discord.Interaction):
            if not interaction.guild:
                await interaction.response.send_message("⚠️ Run within a corporate server!", ephemeral=True)
                return

            cafeteria_ch = find_cafeteria_channel(interaction.guild) or interaction.channel
            await interaction.response.send_message(
                f"☕ **Coffee break called by {interaction.user.mention}!** Head over to {cafeteria_ch.mention}!",
                ephemeral=(cafeteria_ch.id != interaction.channel.id),
            )
            asyncio.create_task(
                self.orchestrator.cafeteria_service.run_coffee_break(
                    target_channel=cafeteria_ch,
                    requested_by=interaction.guild.get_member(interaction.user.id) or interaction.user,
                )
            )

        @self.tree.command(
            name="pantrydebate",
            description="Starts an interactive IT Watercooler Debate in #cafeteria with 🅰️ vs 🅱️ voting",
        )
        @app_commands.describe(topic="Optional custom tech debate topic (or leave blank for random topic)")
        async def pantrydebate_slash(interaction: discord.Interaction, topic: Optional[str] = None):
            if not interaction.guild:
                await interaction.response.send_message("⚠️ Run within a corporate server!", ephemeral=True)
                return

            cafeteria_ch = find_cafeteria_channel(interaction.guild) or interaction.channel
            await interaction.response.send_message(
                f"🗣️ **Watercooler debate initiated!** Check {cafeteria_ch.mention} to vote!",
                ephemeral=(cafeteria_ch.id != interaction.channel.id),
            )
            asyncio.create_task(
                self.orchestrator.cafeteria_service.start_pantry_debate(
                    target_channel=cafeteria_ch,
                    custom_topic=topic,
                    requested_by=interaction.guild.get_member(interaction.user.id) or interaction.user,
                )
            )

        @self.tree.command(
            name="watercooler",
            description="Posts the daily cafeteria snack special and IT workplace trivia",
        )
        async def watercooler_slash(interaction: discord.Interaction):
            if not interaction.guild:
                await interaction.response.send_message("⚠️ Run within a corporate server!", ephemeral=True)
                return

            await interaction.response.defer()
            cafeteria_ch = find_cafeteria_channel(interaction.guild) or interaction.channel
            await self.orchestrator.cafeteria_service.post_watercooler_snack(cafeteria_ch)
            if cafeteria_ch.id != interaction.channel.id:
                await interaction.followup.send(f"🥐 Snack special posted in {cafeteria_ch.mention}!")
            else:
                await interaction.followup.send("🥐 Bon appétit!", ephemeral=True)

        @self.tree.command(
            name="chat",
            description="Chat casually in Discord player Tanglish with Vijay, Sivakarthikeyan, Anirudh, Trisha, etc.",
        )
        @app_commands.describe(
            character="Select which community character or bot to chat with",
            message="Your message to them",
        )
        @app_commands.choices(
            character=[
                app_commands.Choice(name="👑 Vijay (Swagger & Calm)", value="vijay"),
                app_commands.Choice(name="🎤 Sivakarthikeyan (Timing Punch & Trolling)", value="sivakarthikeyan"),
                app_commands.Choice(name="🎵 Anirudh (Rockstar Vibe & BGM)", value="anirudh"),
                app_commands.Choice(name="💅 Trisha (Sarcastic Aesthetic Burns)", value="trisha"),
                app_commands.Choice(name="🎬 Lokesh (Action & Dark Humour)", value="lokesh"),
                app_commands.Choice(name="🏍️ TTF Vasan (299 km/h Hype)", value="ttf_vasan"),
                app_commands.Choice(name="🧠 Pradeep Ranganathan (Sarcastic Logic)", value="pradeep"),
                app_commands.Choice(name="🎨 Mamitha (Aesthetic Teasing)", value="mamitha"),
                app_commands.Choice(name="⚙️ Kayadu (Calm DevOps Savage)", value="kayadu"),
                app_commands.Choice(name="🛡️ Muthazhagi (Strict QA Fire)", value="muthazhagi"),
            ]
        )
        async def chat_slash(interaction: discord.Interaction, character: str, message: str):
            if not interaction.guild:
                await interaction.response.send_message("⚠️ Run within a corporate server!", ephemeral=True)
                return

            await interaction.response.defer()
            await interaction.followup.send(f"💬 *Connecting to {character}...*", ephemeral=True)
            sender_name = interaction.user.display_name
            await self.orchestrator.casual_player_service.chat(
                character_key=character,
                message=message,
                sender_name=sender_name,
                channel=interaction.channel,
            )

        @self.tree.command(
            name="roast",
            description="Drop a savage Tanglish roast on a teammate, code snippet, or topic",
        )
        @app_commands.describe(
            target="Who or what to roast (e.g., @User or 'Friday production deploy')",
            character="Select who should deliver the roast",
            topic="Optional reason or context for the roast",
        )
        @app_commands.choices(
            character=[
                app_commands.Choice(name="🎤 Sivakarthikeyan (Timing Punch Roast)", value="sivakarthikeyan"),
                app_commands.Choice(name="👑 Vijay (Calm Savage Swagger)", value="vijay"),
                app_commands.Choice(name="💅 Trisha (Cool Girl Aesthetic Burn)", value="trisha"),
                app_commands.Choice(name="🎬 Lokesh (Action-Driven Dark Roast)", value="lokesh"),
                app_commands.Choice(name="🧠 Pradeep (Sarcastic Tech Logic)", value="pradeep"),
                app_commands.Choice(name="🏍️ TTF Vasan (299 km/h Hype Roast)", value="ttf_vasan"),
                app_commands.Choice(name="🛡️ Muthazhagi (Strict QA Fire)", value="muthazhagi"),
            ]
        )
        async def roast_slash(
            interaction: discord.Interaction,
            target: str,
            character: Optional[str] = "sivakarthikeyan",
            topic: Optional[str] = None,
        ):
            if not interaction.guild:
                await interaction.response.send_message("⚠️ Run within a corporate server!", ephemeral=True)
                return

            await interaction.response.defer()
            await interaction.followup.send("🔥 *Roast incoming...*", ephemeral=True)
            await self.orchestrator.casual_player_service.roast(
                character_key=character or "sivakarthikeyan",
                target=target,
                topic=topic or "overall coding logic and scene",
                sender_name=interaction.user.display_name,
                channel=interaction.channel,
            )

        @self.tree.command(
            name="banter",
            description="Sparks an interactive 4-line mini roast battle / banter between characters",
        )
        @app_commands.describe(topic="Debate or banter topic (e.g., Tabs vs Spaces, Friday Deploy)")
        async def banter_slash(interaction: discord.Interaction, topic: Optional[str] = None):
            if not interaction.guild:
                await interaction.response.send_message("⚠️ Run within a corporate server!", ephemeral=True)
                return

            debate_topic = topic or "tabs vs spaces and deploy logic"
            await interaction.response.defer()
            await interaction.followup.send(f"⚔️ **Sparks flying! Community Banter initiated on: '{debate_topic}'**")
            asyncio.create_task(
                self.orchestrator.casual_player_service.banter(
                    topic=debate_topic,
                    channel=interaction.channel,
                )
            )

        @self.tree.command(
            name="clash",
            description="Team Vasan vs Team Vijay full-squad witty roast battle",
        )
        @app_commands.describe(topic="Debate or roast topic (e.g., High-speed Deploy vs Clean Logic)")
        async def clash_slash(interaction: discord.Interaction, topic: Optional[str] = None):
            if not interaction.guild:
                await interaction.response.send_message("⚠️ Run within a corporate server!", ephemeral=True)
                return

            debate_topic = topic or "299 speed vs clean logic and deploy war"
            await interaction.response.defer()
            await interaction.followup.send(f"⚔️ **TEAM VASAN VS TEAM VIJAY ROAST CLASH ON: '{debate_topic}'!** 🔥")
            asyncio.create_task(
                self.orchestrator.casual_player_service.clash(
                    topic=debate_topic,
                    channel=interaction.channel,
                )
            )

    async def on_ready(self):
        logger.info(
            f"Agent '{self.agent_config.name}' connected as {self.user} (ID: {self.user.id})"
        )
        self.orchestrator.register_ready_bot(self.agent_config.key, self)

        # Sync TTF Vasan slash commands to the target guild for instant availability
        if self.agent_config.key == "ttf_vasan" and hasattr(self, "tree"):
            try:
                guild_obj = discord.Object(id=self.orchestrator.config.guild_id)
                self.tree.copy_global_to(guild=guild_obj)
                synced = await self.tree.sync(guild=guild_obj)
                logger.info(
                    f"TTF Vasan slash command(s) synced to Guild {self.orchestrator.config.guild_id}: "
                    f"{[c.name for c in synced]}"
                )
            except Exception as exc:
                logger.error(f"Failed to sync slash commands for TTF Vasan: {exc}")

        # Auto-join voice immediately upon login during work shifts (especially Team Vijay)
        target_guild = self.get_guild(self.orchestrator.config.guild_id)
        if not target_guild:
            try:
                target_guild = await self.fetch_guild(self.orchestrator.config.guild_id)
            except Exception:
                target_guild = None

        if target_guild:
            asyncio.create_task(
                self.orchestrator.scheduler_service.handle_bot_login_voice(
                    self.agent_config.key, self, target_guild
                )
            )

    async def on_message(self, message: discord.Message):
        await self.orchestrator.handle_incoming_message(self, message)

    async def on_member_join(self, member: discord.Member):
        if self.agent_config.key == "sadie":
            await self.orchestrator.moderator_service.send_onboarding_greeting(member)
        elif self.agent_config.key == "millie":
            await self.orchestrator.moderator_service.log_member_join(member)

    async def on_member_remove(self, member: discord.Member):
        if self.agent_config.key == "millie":
            await self.orchestrator.moderator_service.log_member_remove(member)

    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if self.agent_config.key == "millie":
            await self.orchestrator.moderator_service.log_member_role_update(before, after)

    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        if self.agent_config.key == "millie":
            await self.orchestrator.moderator_service.log_channel_create(channel)

    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        if self.agent_config.key == "millie":
            await self.orchestrator.moderator_service.log_channel_delete(channel)

    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if self.agent_config.key == "millie":
            await self.orchestrator.moderator_service.log_voice_update(member, before, after)
        # Handle 24/7 instant patrol trigger, follower tracking, and sleep room mute/deaf sync
        if self.agent_config.key == "sadie":
            await self.orchestrator.moderator_service.handle_voice_state_patrol_trigger(member, before, after)
            await self.orchestrator.moderator_service.handle_follower_voice_update(member, before, after)
            await self.orchestrator.moderator_service.sync_moderator_voice_state(member, after)

        # Force Undeafen & Unmute for our bots in Tech Cafe or Working VCs
        if self.user and member.id == self.user.id and after.channel:
            ch_name = after.channel.name.lower()
            cat_name = after.channel.category.name.lower() if after.channel.category else ""
            is_sleep = ("sleep" in ch_name or "night spend" in cat_name)
            is_tech_cafe = (
                "tech cafe" in cat_name
                or ch_name in ("the seven slide", "byte & bit", "the hive", "the hangout zone")
            )
            is_working_vc = (
                "working" in ch_name
                or "team vaasan" in cat_name
                or "team vasan" in cat_name
                or "team vijay" in cat_name
            )

            if not is_sleep and (is_tech_cafe or is_working_vc):
                if after.self_mute or after.self_deaf:
                    try:
                        if hasattr(self, "ws") and self.ws:
                            await self.ws.voice_state(
                                member.guild.id,
                                after.channel.id,
                                self_mute=False,
                                self_deaf=False,
                            )
                    except Exception as exc:
                        logger.debug(f"Could not enforce undeafen/unmute for {self.user.name}: {exc}")


class AgentOrchestrator:
    """
    Coordinates all configured Discord bot clients, multi-agent AI sprints, server rebuilding,
    executive moderation, and the automated 24h IST shift scheduler.
    """

    def __init__(self, config: SystemConfig):
        self.config = config
        self.gemini_service = GeminiService(
            api_key=config.gemini_api_key,
            candidate_models=config.gemini_models,
        )
        self.moderator_service = ModeratorService(self)
        self.cafeteria_service = CafeteriaService(self)
        self.scheduler_service = CompanyScheduler(self)
        self.casual_player_service = CasualPlayerService(self)
        self.clients: Dict[str, VaelkryBotClient] = {}
        self.bot_user_ids: Dict[int, str] = {}
        self.bot_mentions: Dict[str, str] = {}
        self.ready_events: Dict[str, asyncio.Event] = {
            key: asyncio.Event() for key in config.agents.keys()
        }
        self.discussion_lock = asyncio.Lock()
        self.setup_lock = asyncio.Lock()
        self.dev_order = ["ttf_vasan", "pradeep", "mamitha", "kayadu", "muthazhagi"]

    def register_ready_bot(self, agent_key: str, client: VaelkryBotClient):
        self.clients[agent_key] = client
        if client.user:
            self.bot_user_ids[client.user.id] = agent_key
            self.bot_mentions[agent_key] = client.user.mention
        self.ready_events[agent_key].set()

    async def wait_until_all_ready(self, timeout: float = 35.0):
        logger.info(f"Waiting for all {len(self.ready_events)} bots to connect to Discord gateway...")
        tasks = [event.wait() for event in self.ready_events.values()]
        try:
            await asyncio.wait_for(asyncio.gather(*tasks), timeout=timeout)
            logger.info(f"All {len(self.ready_events)} Vaelkry Dev Labs bots are online and operational!")
        except asyncio.TimeoutError:
            missing = [k for k, ev in self.ready_events.items() if not ev.is_set()]
            logger.warning(f"Timeout waiting for bots: {missing}. Proceeding with available bots.")

        # Launch floor-patrol background routine for SadieSink & MillieBobbyBrown
        lead = self.clients.get("sadie") or self.clients.get("ttf_vasan")
        if lead:
            guild_obj = lead.get_guild(self.config.guild_id)
            if guild_obj:
                self.moderator_service.start_patrol_loop(guild_obj)
                # Automatically ensure Team Vijay category and sync all enterprise roles
                asyncio.create_task(ensure_enterprise_roles(guild_obj, self.clients))

    # ==================== SERVER RESET & BLUEPRINT FLOW ====================

    async def execute_blueprint_reset_flow(self, guild: discord.Guild, send_fn):
        if self.setup_lock.locked():
            await send_fn("⚠️ Server rebuild already in progress! Please wait.")
            return

        async with self.setup_lock:
            logger.info(f"Initiating CEO Blueprint Reset & Rebuild for Guild: {guild.name}")
            try:
                hierarchy, launchpad = await reset_and_build_server(guild, send_fn)
                if launchpad:
                    self.config.project_channel_id = launchpad.id
                    logger.info(f"Updated PROJECT_CHANNEL_ID to {launchpad.id} ({launchpad.name})")

                # Re-provision enterprise corporate roles
                await ensure_enterprise_roles(guild, self.clients)

                summary_text = format_blueprint_directory(hierarchy, launchpad)

                # Send completion notice strictly to CEO channel (#yogesh-chat / ID: 1563622902744481812)
                # Keep #announcements strictly clean for official CEO manual announcements only
                ceo_ch = get_ceo_channel(guild)
                if ceo_ch:
                    try:
                        await ceo_ch.send(summary_text)
                    except Exception as exc:
                        logger.warning(f"Failed to post blueprint summary to CEO channel #{ceo_ch.name}: {exc}")

                # Also respond to interaction
                try:
                    await send_fn(summary_text)
                except Exception:
                    pass

                logger.info("CEO Blueprint Reset & Rebuild executed successfully.")
            except Exception as exc:
                logger.exception(f"Error during blueprint rebuild: {exc}")
                try:
                    await send_fn(f"⚠️ **Error resetting server structure:** `{exc}`")
                except Exception:
                    pass

    # ==================== DYNAMIC TEAM CATEGORY FLOW ====================

    async def execute_team_category_flow(self, guild: discord.Guild, team_name: str, send_fn):
        clean_name = team_name.strip().title()
        logger.info(f"Provisioning dynamic team category for: 'Team {clean_name}'")
        try:
            category, channels = await create_dynamic_team_category(guild, clean_name)
            ch_mentions = []
            for ch in channels:
                if isinstance(ch, discord.TextChannel):
                    ch_mentions.append(f"  • {ch.mention} *(Text)*")
                elif isinstance(ch, discord.VoiceChannel):
                    ch_mentions.append(f"  • 🔊 `{ch.name}` *(Voice)*")

            response = (
                f"🚀 **Dynamic Team Provisioning Complete!** 🏢⚡\n\n"
                f"📂 **Category:** `{category.name}` *(Positioned below Team Vaasan)*\n"
                + "\n".join(ch_mentions)
                + f"\n\n*Engineering workspace is live. Sprints can run inside {channels[0].mention}!*"
            )
            await send_fn(response)
        except Exception as exc:
            logger.exception(f"Error provisioning team category: {exc}")
            await send_fn(f"⚠️ **Error provisioning team category:** `{exc}`")

    # ==================== INCOMING MESSAGE ROUTING ====================

    async def handle_incoming_message(self, listener_client: VaelkryBotClient, message: discord.Message):
        if message.author.bot or message.author.id in self.bot_user_ids:
            return

        # 1. Interactive Discord Player Mentions & Direct Replies
        # Allows all dev bots (TTF Vasan, Pradeep, Mamitha, Kayadu, Muthazhagi) to casually reply
        if (
            not message.mention_everyone
            and listener_client.user
            and (
                listener_client.user in message.mentions
                or (message.reference and getattr(message.reference.resolved, "author", None) == listener_client.user)
            )
        ):
            await self.casual_player_service.handle_mention_reply(listener_client, message)
            return

        # Ensure only TTF Vasan handles commands
        if listener_client.agent_config.key != "ttf_vasan":
            return

        content = message.content.strip()

        # Prefix command: !start
        if content.startswith("!start"):
            if not message.guild:
                return
            member = message.guild.get_member(message.author.id) or message.author
            if not is_admin_or_owner(member, message.guild):
                await message.channel.send("🛑 **Access Denied:** Administrator rights required!")
                return
            msg = await self.scheduler_service.start(message.guild)
            await message.channel.send(msg)
            return

        # Prefix command: !stop
        if content.startswith("!stop"):
            if not message.guild:
                return
            member = message.guild.get_member(message.author.id) or message.author
            if not is_admin_or_owner(member, message.guild):
                await message.channel.send("🛑 **Access Denied:** Administrator rights required!")
                return
            msg = await self.scheduler_service.stop(message.guild)
            await message.channel.send(msg)
            return

        # Prefix command: !status
        if content.startswith("!status"):
            if not message.guild:
                return
            status_embed = self.scheduler_service.get_status_embed(message.guild)
            await self.scheduler_service.notify_ceo_channel(message.guild, embed=status_embed)
            ceo_ch = get_ceo_channel(message.guild)
            ceo_mention = ceo_ch.mention if ceo_ch else f"#{CEO_NOTIFICATION_CHANNEL_NAME}"
            await message.channel.send(
                content=f"📊 **Live TTF Vasan operational status log routed strictly to {ceo_mention}!**",
                embed=status_embed,
            )
            return

        # Prefix command: !reset_and_build_server
        if content.startswith("!reset_and_build_server"):
            if not message.guild:
                return
            member = message.guild.get_member(message.author.id) or message.author
            if not is_admin_or_owner(member, message.guild):
                await message.channel.send("🛑 **Access Denied:** Only the Server Owner can reset the server!")
                return
            await self.execute_blueprint_reset_flow(message.guild, message.channel.send)
            return

        # Prefix command: !teamcategory <team_name>
        if content.startswith("!teamcategory"):
            if not message.guild:
                return
            member = message.guild.get_member(message.author.id) or message.author
            if not is_admin_or_owner(member, message.guild):
                await message.channel.send("🛑 **Access Denied:** Administrator rights required!")
                return
            parts = content.split(maxsplit=1)
            if len(parts) < 2 or not parts[1].strip():
                await message.channel.send("⚠️ Usage: `!teamcategory <team_name>` (e.g. `!teamcategory Falcon`)")
                return
            await self.execute_team_category_flow(message.guild, parts[1].strip(), message.channel.send)
            return

        # Prefix command: !follow
        if content.startswith("!follow"):
            if not message.guild:
                return
            member = message.guild.get_member(message.author.id) or message.author
            if not is_admin_or_owner(member, message.guild):
                await message.channel.send("🛑 **Access Denied:** Only CEO or Admin can activate escort mode!")
                return
            _, msg = await self.moderator_service.start_following(member)
            await message.channel.send(msg)
            return

        # Prefix command: !unfollow
        if content.startswith("!unfollow"):
            msg = await self.moderator_service.stop_following(message.guild)
            await message.channel.send(msg)
            return

        # Prefix command: !idcard [member]
        if content.startswith("!idcard"):
            if not message.guild:
                return
            target_mem = message.mentions[0] if message.mentions else (message.guild.get_member(message.author.id) or message.author)
            id_embed = self.moderator_service.get_id_card(target_mem)
            await message.channel.send(embed=id_embed)
            return

        # Prefix command: !provision_roles
        if content.startswith("!provision_roles"):
            if not message.guild:
                return
            member = message.guild.get_member(message.author.id) or message.author
            if not is_admin_or_owner(member, message.guild):
                await message.channel.send("🛑 **Access Denied:** Administrator rights required!")
                return
            roles_map = await ensure_enterprise_roles(message.guild, self.clients)
            role_names = ", ".join(f"`{r}`" for r in roles_map.keys())
            await message.channel.send(
                f"✅ **Enterprise Roles Provisioned & Synchronized!**\n"
                f"Configured roles:\n{role_names}\n"
                f"All bots, CEO, and human software engineers have been provisioned."
            )
            return

        # Prefix commands: !coffee, !chai, !break
        if content.startswith(("!coffee", "!chai", "!break")):
            if not message.guild:
                return
            cafeteria_ch = find_cafeteria_channel(message.guild) or message.channel
            if cafeteria_ch.id != message.channel.id:
                await message.channel.send(f"☕ **Coffee break called by {message.author.mention}!** Head over to {cafeteria_ch.mention}!")
            asyncio.create_task(
                self.cafeteria_service.run_coffee_break(
                    target_channel=cafeteria_ch,
                    requested_by=message.guild.get_member(message.author.id) or message.author,
                )
            )
            return

        # Prefix command: !pantrydebate [topic]
        if content.startswith("!pantrydebate"):
            if not message.guild:
                return
            parts = content.split(maxsplit=1)
            custom_topic = parts[1].strip() if len(parts) > 1 else None
            cafeteria_ch = find_cafeteria_channel(message.guild) or message.channel
            if cafeteria_ch.id != message.channel.id:
                await message.channel.send(f"🗣️ **Watercooler debate initiated!** Check {cafeteria_ch.mention} to vote!")
            asyncio.create_task(
                self.cafeteria_service.start_pantry_debate(
                    target_channel=cafeteria_ch,
                    custom_topic=custom_topic,
                    requested_by=message.guild.get_member(message.author.id) or message.author,
                )
            )
            return

        # Prefix command: !watercooler, !snack
        if content.startswith(("!watercooler", "!snack")):
            if not message.guild:
                return
            cafeteria_ch = find_cafeteria_channel(message.guild) or message.channel
            await self.cafeteria_service.post_watercooler_snack(cafeteria_ch)
            return

        # Casual Player Chat Command: !chat <character> <message>
        if content.startswith("!chat"):
            parts = content.split(maxsplit=2)
            if len(parts) < 3:
                await message.channel.send("⚠️ Usage: `!chat <character> <message>`\nCharacters: `vijay`, `sivakarthikeyan`, `anirudh`, `trisha`, `lokesh`, `pradeep`, `vasan`, `mamitha`")
                return
            char_key = parts[1].lower()
            msg_text = parts[2].strip()
            asyncio.create_task(
                self.casual_player_service.chat(
                    character_key=char_key,
                    message=msg_text,
                    sender_name=message.author.display_name,
                    channel=message.channel,
                )
            )
            return

        # Fast character shortcuts: !v, !sk, !ani, !trisha, !loki
        if content.startswith(("!v ", "!sk ", "!ani ", "!trisha ", "!loki ")):
            prefix, msg_text = content.split(maxsplit=1)
            char_map = {
                "!v": "vijay",
                "!sk": "sivakarthikeyan",
                "!ani": "anirudh",
                "!trisha": "trisha",
                "!loki": "lokesh",
            }
            char_key = char_map.get(prefix.lower(), "vijay")
            asyncio.create_task(
                self.casual_player_service.chat(
                    character_key=char_key,
                    message=msg_text,
                    sender_name=message.author.display_name,
                    channel=message.channel,
                )
            )
            return

        # Casual Player Roast Command: !roast [character] <target>
        if content.startswith("!roast"):
            parts = content.split(maxsplit=2)
            if len(parts) < 2:
                await message.channel.send("⚠️ Usage: `!roast <target>` or `!roast <character> <target>`")
                return
            possible_char = parts[1].lower()
            if possible_char in CASUAL_PLAYER_CHARACTERS and len(parts) > 2:
                char_key = possible_char
                target = parts[2].strip()
            else:
                char_key = "sivakarthikeyan"
                target = content[len("!roast"):].strip()

            asyncio.create_task(
                self.casual_player_service.roast(
                    character_key=char_key,
                    target=target,
                    topic="roast them playfully",
                    sender_name=message.author.display_name,
                    channel=message.channel,
                )
            )
            return

        # Mini Banter Command: !banter [topic]
        if content.startswith("!banter"):
            topic = content[len("!banter"):].strip() or "tabs vs spaces and deploy logic"
            await message.channel.send(f"⚔️ **Community Banter initiated on: '{topic}'**")
            asyncio.create_task(
                self.casual_player_service.banter(
                    topic=topic,
                    channel=message.channel,
                )
            )
            return

        # Squad Clash Command: !clash [topic]
        if content.startswith(("!clash", "!teamclash")):
            topic_str = content.split(maxsplit=1)[1].strip() if len(content.split(maxsplit=1)) > 1 else "299 speed vs clean logic and deploy war"
            await message.channel.send(f"⚔️ **TEAM VASAN VS TEAM VIJAY ROAST CLASH ON: '{topic_str}'!** 🔥")
            asyncio.create_task(
                self.casual_player_service.clash(
                    topic=topic_str,
                    channel=message.channel,
                )
            )
            return

        # AI Sprint Command: !project <idea>
        if content.startswith("!project"):
            ch_name = getattr(message.channel, "name", "").lower()
            is_valid_project_ch = (
                message.channel.id == self.config.project_channel_id
                or ch_name in ("the-launchpad", "working-chat", "project-war-room")
            )

            if not is_valid_project_ch:
                target_mention = f"<#{self.config.project_channel_id}>"
                await message.channel.send(
                    f"⚠️ Mapla, `!project` command-ah {target_mention} or `#working-chat` channel-la run pannunga! 🚀"
                )
                return

            idea = content[len("!project"):].strip()
            if not idea:
                await self.send_help_message(message.channel)
                return

            if self.discussion_lock.locked():
                await message.channel.send(
                    f"⚠️ **Wait panni paaru mapla!** ({message.author.mention}), "
                    f"oru project discussion already process aagittu iruku. "
                    f"Athu mudinja udane unga project-ah thookuvom! 🔥"
                )
                return

            asyncio.create_task(self.run_project_discussion_chain(message, idea))

    async def send_help_message(self, channel: discord.abc.Messageable):
        help_text = (
            "🚀 **Welcome to Vaelkry Dev Labs Enterprise Operations!**\n\n"
            "**Operational & Shift Commands:**\n"
            "• `/start` (or `!start`): Start company operations & activate 24h IST shift scheduler.\n"
            "• `/stop` (or `!stop`): Pause operations & disconnect bots from voice.\n"
            "• `/status` (or `!status`): Generate live TTF Vasan status logs routed to #yogesh-chat.\n"
            "• `/reset_and_build_server` (or `!reset_and_build_server`): Build CEO Handwritten Blueprint.\n"
            "• `/teamcategory <name>` (or `!teamcategory <name>`): Dynamically scale a new team category.\n"
            "• `/follow` (or `!follow`): SadieSink & MillieBobbyBrown escort CEO in voice.\n"
            "• `/unfollow` (or `!unfollow`): Disengage executive voice escort.\n"
            "• `!project <tech idea>`: Launch full 5-agent Tanglish architecture sprint.\n\n"
            "🪪 **Enterprise Identity & Roles:**\n"
            "• `/idcard [member]` (or `!idcard`): View your or another employee's Digital Corporate ID Card.\n"
            "• `/provision_roles` (or `!provision_roles`): Provision and sync all 8 enterprise roles.\n\n"
            "☕ **Common Pantry & Cafeteria (#cafeteria):**\n"
            "• `/coffee` (or `!coffee`, `!chai`, `!break`): Launch a fun 5-agent Tanglish coffee/chai break banter.\n"
            "• `/pantrydebate [topic]` (or `!pantrydebate`): Start an interactive debate with 🅰️ vs 🅱️ voting.\n"
            "• `/watercooler` (or `!watercooler`): Post daily pantry snack special & workplace trivia.\n\n"
            "💬 **Real Discord Player Chat & Roasts:**\n"
            "• `/chat <character> <message>` (or `!chat`): Chat casually in Tanglish with Vijay, SK, Anirudh, Trisha, etc.\n"
            "• `/roast <target> [character]` (or `!roast`): Drop a savage Tanglish roast on a teammate or code.\n"
            "• `/banter [topic]` (or `!banter`): Launch a 4-line mini banter battle between community characters.\n"
            "• `/clash [topic]` (or `!clash`): Full Team Vasan vs Team Vijay witty roast battle.\n"
            "• Shortcuts: `!v <msg>`, `!sk <msg>`, `!ani <msg>`, `!trisha <msg>`, `!loki <msg>`.\n"
            "• Direct mentions: Tag any bot (`@TTF Vasan`, `@Pradeep`, `@SadieSink`, etc.) for an instant comeback!\n\n"
            "**Squad Leadership:**\n"
            "• 🏍️ **TTF Vasan**: Team Lead & Hype Commander\n"
            "• 🧠 **Pradeep Ranganathan**: Tech Lead & Solutions Architect\n"
            "• 🎨 **Mamitha**: UI/UX Designer\n"
            "• ⚙️ **Kayadu**: DevOps & Backend Lead\n"
            "• 🛡️ **Muthazhagi**: QA & Security Lead\n"
            "• 🌟 **SadieSink**: Executive Moderation & Onboarding Desk\n"
            "• 📋 **MillieBobbyBrown**: Chief Audit Officer & Log Custodian\n"
        )
        await channel.send(help_text)

    async def run_project_discussion_chain(self, trigger_message: discord.Message, idea: str):
        async with self.discussion_lock:
            channel_id = trigger_message.channel.id
            logger.info(f"Initiating project chain for: '{idea}' in channel {channel_id}")

            initial_banner = (
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"⚡ **VAELKRY DEV LABS — NEW PROJECT INITIATION** ⚡\n"
                f"👤 **Requested By:** {trigger_message.author.mention}\n"
                f"💡 **Project Concept:** *{idea}*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            )
            lead_client = self.clients.get("ttf_vasan")
            if lead_client:
                lead_ch = lead_client.get_channel(channel_id)
                if lead_ch:
                    await lead_ch.send(initial_banner)

            discussion_history: List[dict] = []

            for agent_key in self.dev_order:
                client = self.clients.get(agent_key)
                if not client:
                    continue

                channel = client.get_channel(channel_id)
                if not channel:
                    continue

                agent_info = AGENT_PROMPTS[agent_key]
                agent_name = client.agent_config.name
                agent_role = client.agent_config.role

                try:
                    typing_duration = random.uniform(2.0, 4.0)
                    prompt = build_agent_prompt(
                        agent_key=agent_key,
                        idea=idea,
                        history=discussion_history,
                        mentions=self.bot_mentions,
                    )

                    async with channel.typing():
                        gemini_task = asyncio.create_task(
                            self.gemini_service.generate_response(prompt=prompt, agent_name=agent_name)
                        )
                        await asyncio.sleep(typing_duration)
                        response_text = await gemini_task

                    header = f"### {agent_info['title']}"
                    formatted_message = f"{header}\n\n{response_text}"
                    await channel.send(formatted_message)

                    discussion_history.append({
                        "speaker": agent_name,
                        "role": agent_role,
                        "text": response_text,
                    })

                except Exception as exc:
                    logger.exception(f"Error during turn for agent '{agent_name}': {exc}")

            if lead_client:
                lead_ch = lead_client.get_channel(channel_id)
                if lead_ch:
                    footer = (
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"🏁 **Vaelkry Dev Labs Project Architecture Review Completed!**\n"
                        f"All specifications locked and validated. Ready for development! 🚀\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                    )
                    await lead_ch.send(footer)


async def main():
    logger.info("Starting Vaelkry Dev Labs Multi-Agent System (Team Vaasan, Team Vijay & Executive Suite)...")

    try:
        config = load_config()
    except Exception as exc:
        logger.critical(f"Configuration error: {exc}")
        sys.exit(1)

    # Initialize complete privileged intents for enterprise moderation & voice
    intents = discord.Intents.default()
    intents.message_content = True
    intents.guilds = True
    intents.members = True
    intents.voice_states = True

    orchestrator = AgentOrchestrator(config)

    # Instantiate all 7 bot clients
    bot_instances: List[tuple[VaelkryBotClient, str]] = []
    for key, agent_cfg in config.agents.items():
        client = VaelkryBotClient(agent_config=agent_cfg, orchestrator=orchestrator, intents=intents)
        orchestrator.clients[key] = client
        bot_instances.append((client, agent_cfg.token))

    # Background connectivity watcher
    asyncio.create_task(orchestrator.wait_until_all_ready())

    try:
        logger.info(f"Launching all {len(bot_instances)} Discord bot clients concurrently via asyncio.gather...")
        await asyncio.gather(*(client.start(token) for client, token in bot_instances))
    except (asyncio.CancelledError, KeyboardInterrupt):
        logger.info("Shutdown signal received. Closing all bot connections...")
    except Exception as exc:
        logger.exception(f"Unexpected runtime error in bot runner: {exc}")
    finally:
        logger.info("Closing all Discord bot clients...")
        # Stop moderator floor-patrol loop
        orchestrator.moderator_service.stop_patrol_loop()

        # Stop scheduler if running
        if orchestrator.scheduler_service.is_active:
            guild_obj = orchestrator.clients["ttf_vasan"].get_guild(config.guild_id)
            if guild_obj:
                await orchestrator.scheduler_service.stop(guild_obj)

        close_tasks = [client.close() for client, _ in bot_instances if not client.is_closed()]
        if close_tasks:
            await asyncio.gather(*close_tasks, return_exceptions=True)
        logger.info("All Vaelkry Dev Labs bot clients closed cleanly.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Process terminated by user.")
