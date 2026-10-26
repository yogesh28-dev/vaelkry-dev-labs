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
import datetime
import logging
import random
import re
import sys
from typing import Dict, List, Optional

import discord
from discord import app_commands

from config import AgentConfig, SystemConfig, load_config
from gemini_service import GeminiService
from agents import (
    AGENT_PROMPTS,
    CASUAL_PLAYER_CHARACTERS,
    CHARACTER_VOICES,
    get_voice_for_character,
    build_agent_prompt,
    build_autonomous_project_brainstorm_prompt,
    build_autonomous_prototype_announcement_prompt,
    build_delegation_prompt,
    classify_task_domain,
    ZONE_WORK_SQUAD,
    ZONE_TECH_CAFE,
    ZONE_NIGHT_SPEND,
)
from server_builder import (
    create_dynamic_team_category,
    ensure_enterprise_roles,
    ensure_team_vijay_category,
    format_blueprint_directory,
    is_admin_or_owner,
    reset_and_build_server,
    spawn_new_squad,
    sync_server_category_layout,
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
from voice_service import VoiceService


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
            name="sync_layout",
            description="Enforces strict category layout ordering and cleans duplicate voice channels (CEO/Admin only)",
        )
        async def sync_layout_slash(interaction: discord.Interaction):
            if not interaction.guild:
                await interaction.response.send_message("⚠️ Run within a corporate server!", ephemeral=True)
                return

            mem = interaction.guild.get_member(interaction.user.id) or interaction.user
            if not is_admin_or_owner(mem, interaction.guild):
                await interaction.response.send_message(
                    "🛑 **Access Denied:** Only the CEO or Admin can synchronize server category layout!",
                    ephemeral=True,
                )
                return

            await interaction.response.defer()
            ordered_cats = await sync_server_category_layout(interaction.guild)
            cat_list = "\n".join(f"• `pos {idx}` **{c.name}**" for idx, c in enumerate(ordered_cats))
            await interaction.followup.send(
                f"✅ **Category Layout & Voice Channels Synchronized!**\n\n"
                f"**Enforced Server Hierarchy (Top to Bottom):**\n"
                f"{cat_list}\n\n"
                f"• Cleaned duplicate voice channels under `Team Vijay` (strictly `Working Vc 1` and `Working Vc 2`).\n"
                f"• Team categories positioned strictly above `Night Spend`.\n"
                f"• `Night Spend` positioned directly above `Vaelkry logs`.\n"
                f"• `Vaelkry logs` positioned at the absolute bottom."
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

        @self.tree.command(
            name="delegate_task",
            description="Smart Squad Delegation: Auto-routes tasks to Team Vaasan or Team Vijay by tech domain",
        )
        @app_commands.describe(
            domain="Tech domain (e.g. Web dev, scraper, automation, backend, mobile app, Flutter, UI design)",
            task_description="Detailed task description and requirements",
        )
        async def delegate_task_slash(
            interaction: discord.Interaction,
            domain: str,
            task_description: str,
        ):
            if not interaction.guild:
                await interaction.response.send_message("⚠️ Run within a corporate server!", ephemeral=True)
                return

            await interaction.response.defer()
            target_team = classify_task_domain(domain, task_description)
            team_map = {
                "team_vasan": ("Team Vaasan", "ttf_vasan", discord.Color.brand_green()),
                "team_vijay": ("Team Vijay", "vijay", discord.Color.gold()),
                "team_messi": ("Team Messi", "messi", discord.Color.from_rgb(0, 168, 255)),
                "team_dhoni": ("Team Dhoni", "dhoni", discord.Color.from_rgb(255, 204, 0)),
            }
            team_display, lead_key, team_color = team_map.get(
                target_team, ("Team Vaasan", "ttf_vasan", discord.Color.brand_green())
            )

            team_cat = discord.utils.find(
                lambda c: c.name.strip().lower() == team_display.lower(),
                interaction.guild.categories,
            )
            target_channel = None
            if team_cat:
                target_channel = discord.utils.find(
                    lambda c: c.name.lower() in ("team-chat", "working-chat"),
                    team_cat.text_channels,
                )

            if not target_channel:
                target_channel = interaction.channel

            prompt = build_delegation_prompt(
                team=target_team,
                domain=domain,
                task_description=task_description,
                requester_name=interaction.user.display_name,
            )
            delegation_text = await self.orchestrator.gemini_service.generate_response(
                prompt=prompt,
                agent_name="SquadDelegation",
            )

            await self.orchestrator.casual_player_service.send_character_chat(
                channel=target_channel,
                character_key=lead_key,
                text=delegation_text,
            )

            import datetime
            confirm_embed = discord.Embed(
                title="🎯 Smart Squad Task Delegated!",
                description=(
                    f"**Task successfully routed by Tech Domain:**\n"
                    f"• **Domain:** `{domain}`\n"
                    f"• **Assigned Squad:** **{team_display}**\n"
                    f"• **Channel:** {target_channel.mention}\n\n"
                    f"The team lead has received the assignment and delegated sub-tasks to the squad!"
                ),
                color=team_color,
                timestamp=datetime.datetime.now(datetime.timezone.utc),
            )
            await interaction.followup.send(embed=confirm_embed)

        @self.tree.command(
            name="spawn_squad",
            description="Dynamic Scaling Engine: Provisions a new engineering squad category, channels & role (Admin/CEO)",
        )
        @app_commands.describe(
            team_name="Name of the new squad (e.g. Falcon, Nova, Cyber)",
            lead_name="Lead of the squad (e.g. Vikram, Surya, Priya)",
        )
        async def spawn_squad_slash(
            interaction: discord.Interaction,
            team_name: str,
            lead_name: str,
        ):
            if not interaction.guild:
                await interaction.response.send_message("⚠️ Run within a corporate server!", ephemeral=True)
                return

            mem = interaction.guild.get_member(interaction.user.id) or interaction.user
            if not is_admin_or_owner(mem, interaction.guild):
                await interaction.response.send_message(
                    "🛑 **Access Denied:** Administrator rights required to spawn new squads!",
                    ephemeral=True,
                )
                return

            await interaction.response.defer()
            category, channels, role = await spawn_new_squad(interaction.guild, team_name, lead_name)
            ch_list = "\n".join(f"• {c.mention} (`{c.name}`)" for c in channels)
            import datetime
            embed = discord.Embed(
                title=f"⚡ New Squad Spawned: {category.name}!",
                description=(
                    f"**Engineering Squad dynamically provisioned!**\n"
                    f"• **Lead:** `{lead_name}`\n"
                    f"• **Role:** {role.mention}\n"
                    f"• **Category:** `{category.name}` (pos `{category.position}`)\n"
                    f"• **Hierarchy Rule:** Strictly positioned **ABOVE 'Night Spend'** in Tier 2.\n\n"
                    f"**Provisioned Channels:**\n{ch_list}"
                ),
                color=role.color if role else discord.Color.brand_green(),
                timestamp=datetime.datetime.now(datetime.timezone.utc),
            )
            await interaction.followup.send(embed=embed)

        @self.tree.command(
            name="executive_dashboard",
            description="Generates and dispatches executive status dashboard to #managers-space and #yogesh-chat",
        )
        async def executive_dashboard_slash(interaction: discord.Interaction):
            if not interaction.guild:
                await interaction.response.send_message("⚠️ Run within a corporate server!", ephemeral=True)
                return

            await interaction.response.defer()
            success, msg = await self.orchestrator.moderator_service.send_executive_dashboard(interaction.guild)
            dashboard_embed = self.orchestrator.moderator_service.generate_executive_dashboard_embed(interaction.guild)
            await interaction.followup.send(content=msg, embed=dashboard_embed)

        @self.tree.command(
            name="movie_hangout",
            description="Tech Cafe Movie Hangout: Picks 2-3 dev bots into The Hangout Zone for a movie watch party",
        )
        async def movie_hangout_slash(interaction: discord.Interaction):
            if not interaction.guild:
                await interaction.response.send_message("⚠️ Run within a corporate server!", ephemeral=True)
                return

            await interaction.response.defer()
            success, msg = await self.orchestrator.scheduler_service.trigger_movie_hangout(interaction.guild)
            await interaction.followup.send(msg)

        @self.tree.command(
            name="autonomous_sprint",
            description="AI-to-AI Autonomous Labs: Squads brainstorm and post open-source boilerplate to #the-launchpad",
        )
        async def autonomous_sprint_slash(interaction: discord.Interaction):
            if not interaction.guild:
                await interaction.response.send_message("⚠️ Run within a corporate server!", ephemeral=True)
                return

            await interaction.response.defer()
            result = await self.orchestrator.run_autonomous_project_cycle(interaction.guild)
            if result:
                await interaction.followup.send(
                    f"🚀 **Autonomous Project Sprint Completed!**\n"
                    f"Prototype **{result['project']}** generated by **{result['team']}** and launched into #{result['channel']}!"
                )
            else:
                await interaction.followup.send("⚠️ Autonomous sprint skipped (client project currently in progress).")

        @self.tree.command(
            name="night_chatter",
            description="Late-Night Banter: Simulates 2-4 bots sneaking out into #cafeteria for late-night chat",
        )
        async def night_chatter_slash(interaction: discord.Interaction):
            if not interaction.guild:
                await interaction.response.send_message("⚠️ Run within a corporate server!", ephemeral=True)
                return

            await interaction.response.defer()
            await interaction.followup.send("🌙 **Late-Night Banter initiated in #cafeteria!** 🤫☕")
            asyncio.create_task(
                self.orchestrator.casual_player_service.run_autonomous_night_chatter(interaction.guild)
            )

        @self.tree.command(
            name="zone_chatter",
            description="3-Zone Autonomous Banter: Simulates realistic conversation in Work Squad, Tech Cafe, or Dorms",
        )
        @app_commands.describe(
            zone="Select the company zone for the autonomous conversation",
        )
        @app_commands.choices(
            zone=[
                app_commands.Choice(name="Zone 1: Work Squad Rooms (Dev Crunch & PRs)", value="work_squad"),
                app_commands.Choice(name="Zone 2: Tech Cafe & Pantry (Chai, Samosa & Banter)", value="tech_cafe"),
                app_commands.Choice(name="Zone 3: Night Spend / Dorms (Late-Night Whispers)", value="night_spend"),
            ]
        )
        async def zone_chatter_slash(interaction: discord.Interaction, zone: Optional[app_commands.Choice[str]] = None):
            if not interaction.guild:
                await interaction.response.send_message("⚠️ Run within a corporate server!", ephemeral=True)
                return

            chosen_zone = zone.value if zone else None
            zone_display = (chosen_zone or "current shift").replace("_", " ").title()
            await interaction.response.defer()
            await interaction.followup.send(f"🏢 **Triggering 3-Zone Autonomous Banter for [{zone_display}]!** 🚀")
            asyncio.create_task(
                self.orchestrator.casual_player_service.run_autonomous_zone_chatter(interaction.guild, zone=chosen_zone)
            )

        # ==================== BIDIRECTIONAL REAL-TIME AI VOICE ENGINE COMMANDS ====================

        @self.tree.command(
            name="voice_speak",
            description="Has an authentic character speak your text aloud in your voice channel via Edge-TTS",
        )
        @app_commands.describe(
            character="Choose the character bot to speak",
            text="The message you want them to speak aloud",
        )
        @app_commands.choices(
            character=[
                app_commands.Choice(name="🌟 Sadie Sink (Clear US Executive)", value="sadie"),
                app_commands.Choice(name="📋 Millie Bobby Brown (Crisp British)", value="millie"),
                app_commands.Choice(name="🎨 Mamitha (Sweet Tanglish +3Hz)", value="mamitha"),
                app_commands.Choice(name="⚙️ Kayadu (Calm Confident Tone)", value="kayadu"),
                app_commands.Choice(name="🛡️ Muthazhagi (Strict Authoritative Tamil)", value="muthazhagi"),
                app_commands.Choice(name="💅 Trisha (Elegant Tone -2Hz)", value="trisha"),
                app_commands.Choice(name="🏍️ TTF Vasan (299 km/h Speed +18%)", value="ttf_vasan"),
                app_commands.Choice(name="🧠 Pradeep (Witty Youth Vibe +4Hz)", value="pradeep"),
                app_commands.Choice(name="👑 Vijay (Deep Bass Composed -8Hz)", value="vijay"),
                app_commands.Choice(name="🎤 Sivakarthikeyan (Jolly Dynamic Inflection)", value="sivakarthikeyan"),
                app_commands.Choice(name="🎵 Anirudh (Energetic Casual +2Hz)", value="anirudh"),
                app_commands.Choice(name="🎬 Lokesh (Cinematic Grounded -6Hz)", value="lokesh"),
                app_commands.Choice(name="⚽ Messi (Calm Focused Tone)", value="messi"),
                app_commands.Choice(name="⚡ Ronaldo (Confident Alpha Loud)", value="ronaldo"),
                app_commands.Choice(name="🚁 Dhoni (Calm Captain Depth -8%)", value="dhoni"),
                app_commands.Choice(name="🔥 Virat (Sharp Punchy +8%)", value="virat"),
                app_commands.Choice(name="🤖 Haaland (Brute Force Data -4Hz)", value="haaland"),
                app_commands.Choice(name="🏎️ Mbappe (Ultra-Fast Edge +12%)", value="mbappe"),
                app_commands.Choice(name="🍔 Rohit (Vadapav Chill -2Hz)", value="rohit"),
                app_commands.Choice(name="⚔️ Jadeja (Sharp Fielding Hunter +2Hz)", value="jadeja"),
                app_commands.Choice(name="🕶️ Hardik (High Swagger All-Rounder +4Hz)", value="hardik"),
                app_commands.Choice(name="🕺 Neymar (Flashy Samba Motion +3Hz)", value="neymar"),
            ]
        )
        async def voice_speak_slash(interaction: discord.Interaction, character: str, text: str):
            if not interaction.guild:
                await interaction.response.send_message("⚠️ Run within a corporate server!", ephemeral=True)
                return

            mem = interaction.guild.get_member(interaction.user.id) or interaction.user
            voice_state = getattr(mem, "voice", None)
            if not voice_state or not voice_state.channel:
                await interaction.response.send_message(
                    "⚠️ **Please join a Voice Channel first** to hear the bot speak!",
                    ephemeral=True,
                )
                return

            vc = voice_state.channel
            profile = get_voice_for_character(character)
            await interaction.response.defer()

            asyncio.create_task(
                self.orchestrator.voice_service.speak_text(
                    voice_channel=vc,
                    character_key=character,
                    text=text,
                )
            )

            embed = discord.Embed(
                title=f"🔊 {profile['name']} Speaking in `{vc.name}`",
                description=f"💬 *\"{text}\"*\n\n"
                            f"**Voice Profile:** `{profile['voice']}`\n"
                            f"**Pitch:** `{profile['pitch']}` | **Rate:** `{profile['rate']}`\n"
                            f"**Tone:** *{profile['tone']}*",
                color=0x2ECC71,
            )
            embed.set_footer(text="Vaelkry Dev Labs Real-Time Voice Engine • Edge-TTS Neural")
            await interaction.followup.send(embed=embed)

        @self.tree.command(
            name="voice_banter",
            description="Sparks spontaneous spoken cross-bot banter in your voice channel with 1.5-3.0s turn-taking",
        )
        @app_commands.describe(
            bot_a="First speaker (or leave blank for random)",
            bot_b="Second speaker (or leave blank for random)",
            topic="Optional debate or banter topic",
        )
        async def voice_banter_slash(
            interaction: discord.Interaction,
            bot_a: Optional[str] = None,
            bot_b: Optional[str] = None,
            topic: Optional[str] = None,
        ):
            if not interaction.guild:
                await interaction.response.send_message("⚠️ Run within a corporate server!", ephemeral=True)
                return

            mem = interaction.guild.get_member(interaction.user.id) or interaction.user
            voice_state = getattr(mem, "voice", None)
            if not voice_state or not voice_state.channel:
                await interaction.response.send_message(
                    "⚠️ **Please join a Voice Channel first** to trigger cross-bot banter!",
                    ephemeral=True,
                )
                return

            vc = voice_state.channel
            first_bot = bot_a or random.choice(["ttf_vasan", "vijay", "messi", "dhoni"])
            second_bot = bot_b or random.choice(["pradeep", "sivakarthikeyan", "ronaldo", "virat"])
            if first_bot == second_bot:
                second_bot = "sivakarthikeyan" if first_bot != "sivakarthikeyan" else "ttf_vasan"

            prof_a = get_voice_for_character(first_bot)
            prof_b = get_voice_for_character(second_bot)

            await interaction.response.defer()

            asyncio.create_task(
                self.orchestrator.voice_service.trigger_cross_bot_banter(
                    voice_channel=vc,
                    bot_a_key=first_bot,
                    bot_b_key=second_bot,
                    topic=topic or "coding speed, design logic and deploy war",
                )
            )

            embed = discord.Embed(
                title=f"⚔️ Voice Banter: {prof_a['name']} vs {prof_b['name']}",
                description=f"📍 **Channel:** `{vc.name}`\n"
                            f"🎙️ **Turn 1:** `{prof_a['name']}` ({prof_a['tone']})\n"
                            f"⏸️ **Turn-taking pause:** `1.5 - 3.0s` (Audio Lock active)\n"
                            f"🎙️ **Turn 2:** `{prof_b['name']}` ({prof_b['tone']})\n"
                            f"🎯 **Topic:** *{topic or 'deploy logic & speed clash'}*",
                color=0xE67E22,
            )
            embed.set_footer(text="Vaelkry VC Dialogue Engine • Bidirectional Turn-Taking")
            await interaction.followup.send(embed=embed)

        @self.tree.command(
            name="voice_listen",
            description="Enables bidirectional real-time speech recognition & sub-2s contextual voice AI replies",
        )
        async def voice_listen_slash(interaction: discord.Interaction):
            if not interaction.guild:
                await interaction.response.send_message("⚠️ Run within a corporate server!", ephemeral=True)
                return

            mem = interaction.guild.get_member(interaction.user.id) or interaction.user
            voice_state = getattr(mem, "voice", None)
            if not voice_state or not voice_state.channel:
                await interaction.response.send_message(
                    "⚠️ **Please join a Voice Channel first** to start real-time voice listening!",
                    ephemeral=True,
                )
                return

            vc = voice_state.channel
            await interaction.response.defer()

            success = self.orchestrator.voice_service.start_listening_in_channel(vc)
            if success:
                embed = discord.Embed(
                    title="🎙️ Bidirectional AI Voice Engine Active",
                    description=f"✅ Listening to human speech in `{vc.name}`!\n\n"
                                f"• Speak naturally in English, Tanglish, or Tamil.\n"
                                f"• Say a bot's name (e.g. *\"Hey Vasan\"*, *\"Vijay bro\"*, *\"Pradeep review this\"*) to address them specifically.\n"
                                f"• Context is forwarded to Gemini AI, and the bot will reply aloud in **under 2 seconds**!\n"
                                f"• Run `/voice_stop` or `!vcstop` at any time to disconnect listening.",
                    color=0x9B59B6,
                )
                embed.set_footer(text="discord-ext-voice-recv + Google STT + Gemini AI + Edge-TTS")
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send("⚠️ Could not activate voice listening in this channel.")

        @self.tree.command(
            name="voice_stop",
            description="Stops active voice speech and listening in your voice channel",
        )
        async def voice_stop_slash(interaction: discord.Interaction):
            if not interaction.guild:
                await interaction.response.send_message("⚠️ Run within a corporate server!", ephemeral=True)
                return

            mem = interaction.guild.get_member(interaction.user.id) or interaction.user
            voice_state = getattr(mem, "voice", None)
            target_vc = voice_state.channel if (voice_state and voice_state.channel) else None

            if target_vc:
                self.orchestrator.voice_service.stop_listening_in_channel(target_vc)
                await interaction.response.send_message(
                    f"🛑 **Voice engine stopped in `{target_vc.name}`.**",
                )
            else:
                await interaction.response.send_message("⚠️ You are not in a voice channel.")

        @self.tree.command(
            name="voice_profiles",
            description="Displays all 22 authentic female and male neural voice presets (pitch, speed, tone)",
        )
        async def voice_profiles_slash(interaction: discord.Interaction):
            embed = discord.Embed(
                title="🎙️ Vaelkry Dev Labs - Neural Voice Catalog",
                description="All 22 bot personas configured with authentic Microsoft Edge-TTS / Azure neural voices, custom pitch offsets, and dynamic speed rates:",
                color=0x3498DB,
            )

            female_lines = []
            for k, prof in CHARACTER_VOICES.items():
                if prof.get("gender") == "female":
                    female_lines.append(
                        f"• **{prof['name']}**: `{prof['voice']}` (Pitch: `{prof['pitch']}`, Rate: `{prof['rate']}`) — *{prof['tone']}*"
                    )
            embed.add_field(
                name="👩 Authentic Female Bot Voices",
                value="\n".join(female_lines),
                inline=False,
            )

            male_lines = []
            for k, prof in CHARACTER_VOICES.items():
                if prof.get("gender") == "male":
                    male_lines.append(
                        f"• **{prof['name']}**: `{prof['voice']}` (Pitch: `{prof['pitch']}`, Rate: `{prof['rate']}`) — *{prof['tone']}*"
                    )
            embed.add_field(
                name="👨 Authentic Male Bot Voices",
                value="\n".join(male_lines),
                inline=False,
            )

            embed.set_footer(text="Zero-bloat streaming • Sub-2s latency • Dynamic pitch/rate modulation")
            await interaction.response.send_message(embed=embed)

        @self.tree.command(
            name="wake_all_vc",
            description="Wakes all 22 bots, moves them to target VC (or Tech Cafe), undeafens/unmutes them & overrides sleep",
        )
        @app_commands.describe(
            target_channel="Voice channel to gather all bots in (defaults to your current VC or Tech Cafe)",
        )
        async def wake_all_vc_slash(
            interaction: discord.Interaction,
            target_channel: Optional[discord.VoiceChannel] = None,
        ):
            if not interaction.guild:
                await interaction.response.send_message("⚠️ Run within a corporate server!", ephemeral=True)
                return

            mem = interaction.guild.get_member(interaction.user.id) or interaction.user
            if not is_admin_or_owner(mem, interaction.guild):
                await interaction.response.send_message(
                    "🛑 **Access Denied:** Only the CEO or Admin can trigger Master VC Wakeup!",
                    ephemeral=True,
                )
                return

            await interaction.response.defer()

            # If user did not provide target_channel, check if user is currently in a VC
            dest_vc = target_channel
            if not dest_vc:
                vstate = getattr(mem, "voice", None)
                if vstate and vstate.channel and isinstance(vstate.channel, discord.VoiceChannel):
                    dest_vc = vstate.channel

            count, resolved_vc = await self.orchestrator.scheduler_service.wake_all_bots_to_vc(
                guild=interaction.guild,
                target_vc=dest_vc,
            )

            # Ensure voice listener is actively listening so TTF Vasan and team can hear speech and execute tasks
            if hasattr(self.orchestrator, "voice_service") and self.orchestrator.voice_service:
                try:
                    self.orchestrator.voice_service.start_listening_in_channel(resolved_vc)
                except Exception as l_err:
                    logger.warning(f"Failed to auto-start voice listening after slash wakeup: {l_err}")

            embed = discord.Embed(
                title="⚡ Master VC Wakeup & Override Activated",
                description=(
                    f"**Successfully initiated staggered gathering of {count}/22 bots into `{resolved_vc.name}`!**\n\n"
                    f"• **Human Jitter:** Bots filtering into voice with realistic **1s to 10s staggered delays**.\n"
                    f"• **Voice State:** Strictly set to `mute=False, deafen=False` (undeafened & unmuted).\n"
                    f"• **TTF Vasan & Squad:** Actively present in voice channel, listening and ready for tasks.\n"
                    f"• **Sleep Override:** `ACTIVE` (scheduler will preserve bots awake and active in this VC).\n"
                    f"• **Ready for Voice:** Speak to any bot using `/voice_speak` or chat via `/voice_listen`!"
                ),
                color=0xF1C40F,
            )
            embed.set_footer(text="Vaelkry Dev Labs Master Voice Override • All 22 Bots Online")
            await interaction.followup.send(embed=embed)

        @self.tree.command(
            name="wakevc",
            description="Master VC Wakeup (Alias): Wakes all bots, moves to target VC, unmutes & undeafens them",
        )
        @app_commands.describe(
            target_channel="Voice channel to gather all bots in (defaults to your current VC or Tech Cafe)",
        )
        async def wakevc_slash(
            interaction: discord.Interaction,
            target_channel: Optional[discord.VoiceChannel] = None,
        ):
            await wake_all_vc_slash(interaction, target_channel=target_channel)

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
            if self.agent_config.key == "ttf_vasan":
                asyncio.create_task(sync_server_category_layout(target_guild))
            asyncio.create_task(
                self.orchestrator.scheduler_service.handle_bot_login_voice(
                    self.agent_config.key, self, target_guild
                )
            )
            # Ensure 24/7 autonomous background chatter loop is running
            self.orchestrator.casual_player_service.ensure_autonomous_chatting_loop()

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

        # Immediate Ceo Vc Eviction: If any bot other than Sadie and Millie is inside Ceo Vc, evict instantly!
        if member.bot and after.channel:
            from scheduler_service import is_ceo_vc, EXECUTIVE_BOT_KEYS, _normalize_bot_key
            if is_ceo_vc(after.channel):
                bot_k = self.orchestrator.bot_user_ids.get(member.id, "")
                if not bot_k:
                    for k, cl in self.orchestrator.clients.items():
                        if cl.user and cl.user.id == member.id:
                            bot_k = k
                            break
                if _normalize_bot_key(bot_k).lower() not in EXECUTIVE_BOT_KEYS:
                    asyncio.create_task(
                        self.orchestrator.scheduler_service.evict_unauthorized_bots_from_ceo_vc(member.guild)
                    )

        # Responsive Live Mic Listening: dynamically listen when humans enter/leave VC
        if self.agent_config.key == "ttf_vasan":
            self.orchestrator.voice_service.handle_voice_state_update(member, before, after)

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
                or any(t in cat_name for t in ("team vaasan", "team vasan", "team vijay", "team messi", "team dhoni"))
            )

            is_override = getattr(self.orchestrator.scheduler_service, "voice_override_active", False)

            if is_override or (not is_sleep and (is_tech_cafe or is_working_vc)):
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
        self.voice_service = VoiceService(self)
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
                # Automatically enforce strict category layout order and sync all enterprise roles on startup
                asyncio.create_task(sync_server_category_layout(guild_obj))
                asyncio.create_task(ensure_enterprise_roles(guild_obj, self.clients))
                self.start_autonomous_labs_loop(guild_obj)

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

    # ==================== AI-TO-AI AUTONOMOUS PROJECTS ====================

    async def run_autonomous_project_cycle(self, guild: discord.Guild) -> Optional[dict]:
        """
        AI-to-AI Autonomous Projects:
        Triggers when no client tasks are active:
        1. Squad members in their respective working chats brainstorm small open-source utilities or UI boilerplate ideas.
        2. Generate modular boilerplate code drafts and post a prototype announcement into #the-launchpad.
        """
        if self.discussion_lock.locked():
            logger.info("Client project sprint active. Skipping autonomous sprint cycle.")
            return None

        team = random.choice(["team_vasan", "team_vijay", "team_messi", "team_dhoni"])
        team_cat_map = {
            "team_vasan": "Team Vaasan",
            "team_vijay": "Team Vijay",
            "team_messi": "Team Messi",
            "team_dhoni": "Team Dhoni",
        }
        team_cat_name = team_cat_map.get(team, "Team Vaasan")
        team_cat = discord.utils.find(lambda c: c.name.strip().lower() == team_cat_name.lower(), guild.categories)
        if not team_cat:
            return None

        working_ch = discord.utils.find(
            lambda c: any(w in c.name.lower() for w in ("working-chat", "team-chat")),
            team_cat.text_channels,
        )
        if not working_ch:
            return None

        # 1. Squad members in working chat brainstorm small open-source utilities
        brainstorm_prompt = build_autonomous_project_brainstorm_prompt(team)
        try:
            brainstorm_raw = await self.gemini_service.generate_response(
                prompt=brainstorm_prompt,
                agent_name="AutonomousBrainstorm",
            )
            for line in brainstorm_raw.splitlines():
                line = line.strip()
                if not line:
                    continue
                match = re.match(r"^\[([a-zA-Z0-9_]+)\]:\s*(.+)$", line)
                if match:
                    char_k = match.group(1).lower().strip()
                    char_msg = match.group(2).strip()
                    await self.casual_player_service.send_character_chat(working_ch, char_k, char_msg)
                    await asyncio.sleep(1.0)
        except Exception as b_exc:
            logger.warning(f"Error during autonomous brainstorm dialogue: {b_exc}")

        # 2. Select open-source utility idea
        project_concepts = [
            ("Vaelkry Micro-Auth", "Next.js 15, FastAPI, Redis, JWT", "Zero-config stateless authentication with automated refresh-token rotation"),
            ("Vaelkry GlassUI Kit", "Flutter 3.x, Dart, Glassmorphism", "High-performance modular glassmorphism widget library with fluid motion dynamics"),
            ("Vaelkry ScraperEngine", "Python 3.12, Playwright, Redis, Docker", "Distributed async web crawler with anti-bot rate-limit evasion & proxy rotation"),
            ("Vaelkry DynamicTheme", "React 19, Tailwind CSS v4, TypeScript", "Cyber-mint dark mode design system with accessible tokenized color variables"),
        ]
        p_name, p_stack, p_desc = random.choice(project_concepts)

        # 3. Generate modular boilerplate code drafts and prototype announcement
        announcement_prompt = build_autonomous_prototype_announcement_prompt(
            project_name=p_name,
            tech_stack=p_stack,
            description=p_desc,
            team=team,
        )
        try:
            announcement_text = await self.gemini_service.generate_response(
                prompt=announcement_prompt,
                agent_name="AutonomousPrototype",
            )
        except Exception as g_exc:
            logger.error(f"Failed to generate autonomous prototype: {g_exc}")
            return None

        # 4. Post into #the-launchpad
        launchpad = discord.utils.find(
            lambda c: "launchpad" in c.name.lower(),
            guild.text_channels,
        ) or working_ch

        embed = discord.Embed(
            title=f"🚀 VAELKRY AUTONOMOUS LABS — PROTOTYPE RELEASE: {p_name}",
            description=announcement_text,
            color=discord.Color.brand_green() if team == "team_vasan" else discord.Color.gold(),
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.add_field(name="Author Squad", value=f"**{team_cat_name}**", inline=True)
        embed.add_field(name="Tech Stack", value=f"`{p_stack}`", inline=True)
        embed.add_field(name="Repository Template", value=f"`github.com/vaelkry-labs/{p_name.lower().replace(' ', '-')}`", inline=False)
        embed.set_footer(text="Autonomous Engineering Loop • Vaelkry Dev Labs HQ")
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        lead_client = self.clients.get("ttf_vasan" if team == "team_vasan" else "vijay") or next(iter(self.clients.values()), None)
        target_send_ch = lead_client.get_channel(launchpad.id) if lead_client else launchpad
        if target_send_ch:
            await target_send_ch.send(embed=embed)

        logger.info(f"Autonomous prototype '{p_name}' successfully launched into #{launchpad.name}!")
        return {"project": p_name, "team": team_cat_name, "channel": launchpad.name}

    def start_autonomous_labs_loop(self, guild: discord.Guild):
        """Starts the autonomous idle project background routine."""
        if hasattr(self, "_autonomous_task") and self._autonomous_task and not self._autonomous_task.done():
            return

        async def _autonomous_loop():
            await asyncio.sleep(60.0)
            while True:
                try:
                    await asyncio.sleep(random.uniform(2700.0, 4500.0))
                    if self.scheduler_service.is_active and not self.discussion_lock.locked():
                        logger.info("Autonomous Labs Loop: checking idle sprint opportunity...")
                        await self.run_autonomous_project_cycle(guild)
                except asyncio.CancelledError:
                    break
                except Exception as loop_exc:
                    logger.warning(f"Error in autonomous labs loop: {loop_exc}")
                    await asyncio.sleep(60.0)

        self._autonomous_task = asyncio.create_task(_autonomous_loop())

    # ==================== INCOMING MESSAGE ROUTING ====================

    async def handle_incoming_message(self, listener_client: VaelkryBotClient, message: discord.Message):
        if message.author.bot or message.author.id in self.bot_user_ids:
            return

        # 0. Selective contextual reaction emojis (20-30% organic chance)
        if listener_client.agent_config.key == "ttf_vasan":
            asyncio.create_task(self.casual_player_service.handle_contextual_reaction(message))

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

        # 2. Late-Night & Cafeteria User Chat / @everyone Trigger Support:
        # When a user types in #cafeteria or pings @everyone, 1-2 random awake bots reply back naturally
        ch_name = getattr(message.channel, "name", "").lower()
        is_cafeteria = ch_name in ("cafeteria", "common-pantry", "pantry")
        is_everyone_ping = message.mention_everyone

        if (is_cafeteria or is_everyone_ping) and not content.startswith("!"):
            asyncio.create_task(
                self.casual_player_service.handle_cafeteria_user_chat(message)
            )
            return

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

        # Prefix command: !sync_layout, !synclayout
        if content.startswith(("!sync_layout", "!synclayout")):
            if not message.guild:
                return
            member = message.guild.get_member(message.author.id) or message.author
            if not is_admin_or_owner(member, message.guild):
                await message.channel.send("🛑 **Access Denied:** Administrator rights required!")
                return
            ordered_cats = await sync_server_category_layout(message.guild)
            cat_list = "\n".join(f"• `pos {idx}` **{c.name}**" for idx, c in enumerate(ordered_cats))
            await message.channel.send(
                f"✅ **Category Layout & Voice Channels Synchronized!**\n\n"
                f"**Enforced Server Hierarchy (Top to Bottom):**\n"
                f"{cat_list}\n\n"
                f"• Cleaned duplicate voice channels under `Team Vijay` (strictly `Working Vc 1` and `Working Vc 2`).\n"
                f"• Team categories positioned strictly above `Night Spend`.\n"
                f"• `Night Spend` positioned directly above `Vaelkry logs`.\n"
                f"• `Vaelkry logs` positioned at the absolute bottom."
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
                await message.channel.send(
                    "⚠️ Usage: `!chat <character> <message>`\n"
                    "Characters: `messi`, `ronaldo`, `neymar`, `haaland`, `mbappe`, `dhoni`, `virat`, `rohit`, `jadeja`, `hardik`, "
                    "`vijay`, `sivakarthikeyan`, `anirudh`, `trisha`, `lokesh`, `vasan`, `pradeep`, `mamitha`"
                )
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

        # Fast character shortcuts for all squads
        fast_shortcuts = (
            "!v ", "!sk ", "!ani ", "!trisha ", "!loki ",
            "!messi ", "!cr7 ", "!ronaldo ", "!neymar ", "!haaland ", "!mbappe ",
            "!dhoni ", "!msd ", "!virat ", "!vk ", "!rohit ", "!hitman ", "!jaddu ", "!jadeja ", "!hardik ",
            "!vasan ", "!pradeep ", "!mamitha ", "!kayadu ", "!muthu "
        )
        if content.startswith(fast_shortcuts):
            prefix, msg_text = content.split(maxsplit=1)
            char_map = {
                "!v": "vijay",
                "!sk": "sivakarthikeyan",
                "!ani": "anirudh",
                "!trisha": "trisha",
                "!loki": "lokesh",
                "!messi": "messi",
                "!cr7": "ronaldo",
                "!ronaldo": "ronaldo",
                "!neymar": "neymar",
                "!haaland": "haaland",
                "!mbappe": "mbappe",
                "!dhoni": "dhoni",
                "!msd": "dhoni",
                "!virat": "virat",
                "!vk": "virat",
                "!rohit": "rohit",
                "!hitman": "rohit",
                "!jaddu": "jadeja",
                "!jadeja": "jadeja",
                "!hardik": "hardik",
                "!vasan": "ttf_vasan",
                "!pradeep": "pradeep",
                "!mamitha": "mamitha",
                "!kayadu": "kayadu",
                "!muthu": "muthazhagi",
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

        # Late-Night Banter Command: !nightchatter, !night_chatter
        if content.startswith(("!nightchatter", "!night_chatter")):
            if not message.guild:
                return
            await message.channel.send("🌙 **Late-night chatter initiated in #cafeteria!** 🤫☕")
            asyncio.create_task(
                self.casual_player_service.run_autonomous_night_chatter(message.guild)
            )
            return

        # 3-Zone Autonomous Banter Command: !zonechatter, !zone_chatter [work|cafe|night]
        if content.startswith(("!zonechatter", "!zone_chatter")):
            if not message.guild:
                return
            parts = content.split()
            requested_zone = None
            if len(parts) > 1:
                z_arg = parts[1].lower().strip()
                if any(w in z_arg for w in ("work", "squad", "crunch", "dev", "1")):
                    requested_zone = ZONE_WORK_SQUAD
                elif any(w in z_arg for w in ("cafe", "tech", "pantry", "chai", "2")):
                    requested_zone = ZONE_TECH_CAFE
                elif any(w in z_arg for w in ("night", "spend", "sleep", "dorm", "whisper", "3")):
                    requested_zone = ZONE_NIGHT_SPEND

            zone_name = (requested_zone or "Current Shift Zone").replace("_", " ").title()
            await message.channel.send(f"🏢 **Triggering 3-Zone Autonomous Banter for [{zone_name}]!** 🚀")
            asyncio.create_task(
                self.casual_player_service.run_autonomous_zone_chatter(message.guild, zone=requested_zone)
            )
            return

        # ==================== VOICE ENGINE TEXT COMMANDS ====================

        # Voice Speech: !speak <bot> <text> or !say <bot> <text>
        if content.startswith(("!speak", "!say")):
            parts = content.split(maxsplit=2)
            if len(parts) < 3:
                await message.channel.send("⚠️ Usage: `!speak <bot_name> <message>` (e.g. `!speak vijay all is well nanba`)")
                return

            mem = message.guild.get_member(message.author.id) if message.guild else message.author
            voice_state = getattr(mem, "voice", None)
            if not voice_state or not voice_state.channel:
                await message.channel.send("⚠️ **Please join a Voice Channel first** to hear the bot speak!")
                return

            bot_arg = parts[1].lower().strip()
            text_arg = parts[2].strip()
            prof = get_voice_for_character(bot_arg)

            asyncio.create_task(
                self.voice_service.speak_text(
                    voice_channel=voice_state.channel,
                    character_key=bot_arg,
                    text=text_arg,
                )
            )
            await message.channel.send(f"🔊 **{prof['name']}** speaking in `{voice_state.channel.name}`: *\"{text_arg}\"*")
            return

        # Voice Banter: !vcbanter [bot_a] [bot_b] [topic]
        if content.startswith(("!vcbanter", "!voicebanter")):
            mem = message.guild.get_member(message.author.id) if message.guild else message.author
            voice_state = getattr(mem, "voice", None)
            if not voice_state or not voice_state.channel:
                await message.channel.send("⚠️ **Please join a Voice Channel first** to start VC banter!")
                return

            subparts = content.split(maxsplit=3)
            bot_a = subparts[1].lower() if len(subparts) > 1 and not subparts[1].startswith("-") else "ttf_vasan"
            bot_b = subparts[2].lower() if len(subparts) > 2 else "pradeep"
            topic_str = subparts[3] if len(subparts) > 3 else "299 speed vs clean logic and deploy war"

            prof_a = get_voice_for_character(bot_a)
            prof_b = get_voice_for_character(bot_b)

            asyncio.create_task(
                self.voice_service.trigger_cross_bot_banter(
                    voice_channel=voice_state.channel,
                    bot_a_key=bot_a,
                    bot_b_key=bot_b,
                    topic=topic_str,
                )
            )
            await message.channel.send(
                f"⚔️ **Voice Banter Triggered in `{voice_state.channel.name}`:**\n"
                f"• `{prof_a['name']}` vs `{prof_b['name']}` (1.5-3.0s turn-taking audio lock active)\n"
                f"• Topic: *{topic_str}*"
            )
            return

        # Voice Listen: !vclisten (Start Real-Time Human Speech Recognition & Sub-2s AI Reply)
        if content.startswith(("!vclisten", "!voicerecv")):
            mem = message.guild.get_member(message.author.id) if message.guild else message.author
            voice_state = getattr(mem, "voice", None)
            if not voice_state or not voice_state.channel:
                await message.channel.send("⚠️ **Please join a Voice Channel first** to start real-time listening!")
                return

            vc = voice_state.channel
            success = self.voice_service.start_listening_in_channel(vc)
            if success:
                await message.channel.send(
                    f"🎙️ **Bidirectional AI Voice Engine Active in `{vc.name}`!**\n"
                    f"• Listening to human speech in real-time.\n"
                    f"• Address any bot by name (*\"Hey Vasan\"*, *\"Vijay bro\"*, *\"Pradeep review this\"*) or speak naturally.\n"
                    f"• Continuous voice responses delivered in **under 2 seconds**!\n"
                    f"• Type `!vcstop` to stop listening."
                )
            else:
                await message.channel.send("⚠️ Could not activate voice listening in this channel.")
            return

        # Voice Stop: !vcstop
        if content.startswith(("!vcstop", "!vcdisconnect")):
            mem = message.guild.get_member(message.author.id) if message.guild else message.author
            voice_state = getattr(mem, "voice", None)
            target_vc = voice_state.channel if (voice_state and voice_state.channel) else None
            if target_vc:
                self.voice_service.stop_listening_in_channel(target_vc)
                await message.channel.send(f"🛑 **Voice engine stopped in `{target_vc.name}`.**")
            else:
                await message.channel.send("⚠️ You are not in a voice channel.")
            return

        # Voice Profiles Catalog: !voices
        if content.startswith("!voices"):
            embed = discord.Embed(
                title="🎙️ Vaelkry Dev Labs - Neural Voice Catalog",
                description="All 22 bot personas configured with authentic Microsoft Edge-TTS / Azure neural voices, custom pitch offsets, and dynamic speed rates:",
                color=0x3498DB,
            )
            females = [
                f"• **{p['name']}**: `{p['voice']}` (Pitch: `{p['pitch']}`, Rate: `{p['rate']}`) — *{p['tone']}*"
                for p in CHARACTER_VOICES.values() if p.get("gender") == "female"
            ]
            males = [
                f"• **{p['name']}**: `{p['voice']}` (Pitch: `{p['pitch']}`, Rate: `{p['rate']}`) — *{p['tone']}*"
                for p in CHARACTER_VOICES.values() if p.get("gender") == "male"
            ]
            embed.add_field(name="👩 Female Bot Voices", value="\n".join(females), inline=False)
            embed.add_field(name="👨 Male Bot Voices", value="\n".join(males), inline=False)
            embed.set_footer(text="Zero-bloat streaming • Sub-2s latency • Dynamic pitch/rate modulation")
            await message.channel.send(embed=embed)
            return

        # Master VC Wakeup & Override Command: !wakevc [optional_channel_name] or !unmuteall
        if content.startswith(("!wakevc", "!unmuteall", "!wake_all_vc", "!wakeall")):
            if not message.guild:
                return

            mem = message.guild.get_member(message.author.id) if message.guild else message.author
            if not is_admin_or_owner(mem, message.guild):
                await message.channel.send("🛑 **Access Denied:** Only the CEO or Admin can execute `!wakevc`!")
                return

            parts = content.split(maxsplit=1)
            target_vc = None
            if len(parts) > 1:
                query = parts[1].strip().lower()
                target_vc = discord.utils.find(
                    lambda c: query in c.name.lower() and isinstance(c, discord.VoiceChannel),
                    message.guild.voice_channels,
                )

            if not target_vc:
                vstate = getattr(mem, "voice", None)
                if vstate and vstate.channel and isinstance(vstate.channel, discord.VoiceChannel):
                    target_vc = vstate.channel

            count, resolved_vc = await self.scheduler_service.wake_all_bots_to_vc(
                guild=message.guild,
                target_vc=target_vc,
            )

            # Ensure voice listener is actively listening so TTF Vasan and team can hear speech and execute tasks
            if hasattr(self, "voice_service") and self.voice_service:
                try:
                    self.voice_service.start_listening_in_channel(resolved_vc)
                except Exception as l_err:
                    logger.warning(f"Failed to auto-start voice listening after !wakevc: {l_err}")

            embed = discord.Embed(
                title="⚡ Master VC Wakeup & Override Activated",
                description=(
                    f"**Successfully initiated staggered gathering of {count}/22 bots into `{resolved_vc.name}`!**\n\n"
                    f"• **Human Jitter:** Bots filtering into voice with realistic **1s to 10s staggered delays**.\n"
                    f"• **Voice State:** All bots explicitly **unmuted & undeafened** (`mute=False, deafen=False`).\n"
                    f"• **Sleep Override:** `ACTIVE` (scheduler will preserve bots awake and active in this VC).\n"
                    f"• **Next Steps:** Say `!speak vijay all is well` or `!vclisten` to talk directly!"
                ),
                color=0xF1C40F,
            )
            embed.set_footer(text="Vaelkry Dev Labs Master Voice Override • All 22 Bots Online")
            await message.channel.send(embed=embed)
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
            return

        # Prefix command: !delegate_task <domain> <task>, !delegate
        if content.startswith(("!delegate_task", "!delegate")):
            if not message.guild:
                return
            parts = content.split(maxsplit=2)
            if len(parts) < 3:
                await message.channel.send("⚠️ Usage: `!delegate_task <domain> <task description>` (e.g. `!delegate_task mobile Flutter glassmorphic drawer`)")
                return
            domain_arg = parts[1].strip()
            task_arg = parts[2].strip()

            target_team = classify_task_domain(domain_arg, task_arg)
            team_display = "Team Vaasan" if target_team == "team_vasan" else "Team Vijay"
            lead_key = "ttf_vasan" if target_team == "team_vasan" else "vijay"

            team_cat = discord.utils.find(
                lambda c: c.name.strip().lower() == team_display.lower(),
                message.guild.categories,
            )
            target_channel = None
            if team_cat:
                target_channel = discord.utils.find(
                    lambda c: c.name.lower() in ("team-chat", "working-chat"),
                    team_cat.text_channels,
                )
            if not target_channel:
                target_channel = message.channel

            prompt = build_delegation_prompt(
                team=target_team,
                domain=domain_arg,
                task_description=task_arg,
                requester_name=message.author.display_name,
            )
            delegation_text = await self.gemini_service.generate_response(
                prompt=prompt,
                agent_name="SquadDelegation",
            )
            await self.casual_player_service.send_character_chat(
                channel=target_channel,
                character_key=lead_key,
                text=delegation_text,
            )

            confirm_embed = discord.Embed(
                title="🎯 Smart Squad Task Delegated!",
                description=(
                    f"**Task successfully routed by Tech Domain:**\n"
                    f"• **Domain:** `{domain_arg}`\n"
                    f"• **Assigned Squad:** **{team_display}**\n"
                    f"• **Channel:** {target_channel.mention}\n\n"
                    f"The team lead has received the assignment and delegated sub-tasks to the squad!"
                ),
                color=discord.Color.brand_green() if target_team == "team_vasan" else discord.Color.gold(),
                timestamp=datetime.datetime.now(datetime.timezone.utc),
            )
            await message.channel.send(embed=confirm_embed)
            return

        # Prefix command: !spawn_squad <team_name> <lead_name>
        if content.startswith("!spawn_squad"):
            if not message.guild:
                return
            member = message.guild.get_member(message.author.id) or message.author
            if not is_admin_or_owner(member, message.guild):
                await message.channel.send("🛑 **Access Denied:** Administrator rights required!")
                return
            parts = content.split(maxsplit=2)
            if len(parts) < 3:
                await message.channel.send("⚠️ Usage: `!spawn_squad <team_name> <lead_name>` (e.g. `!spawn_squad Falcon Vikram`)")
                return
            team_arg = parts[1].strip()
            lead_arg = parts[2].strip()

            category, channels, role = await spawn_new_squad(message.guild, team_arg, lead_arg)
            ch_list = "\n".join(f"• {c.mention} (`{c.name}`)" for c in channels)
            embed = discord.Embed(
                title=f"⚡ New Squad Spawned: {category.name}!",
                description=(
                    f"**Engineering Squad dynamically provisioned!**\n"
                    f"• **Lead:** `{lead_arg}`\n"
                    f"• **Role:** {role.mention}\n"
                    f"• **Category:** `{category.name}` (pos `{category.position}`)\n"
                    f"• **Hierarchy Rule:** Strictly positioned **ABOVE 'Night Spend'** in Tier 2.\n\n"
                    f"**Provisioned Channels:**\n{ch_list}"
                ),
                color=role.color if role else discord.Color.brand_green(),
                timestamp=datetime.datetime.now(datetime.timezone.utc),
            )
            await message.channel.send(embed=embed)
            return

        # Prefix command: !executive_dashboard, !dashboard
        if content.startswith(("!executive_dashboard", "!dashboard")):
            if not message.guild:
                return
            success, msg = await self.moderator_service.send_executive_dashboard(message.guild)
            dashboard_embed = self.moderator_service.generate_executive_dashboard_embed(message.guild)
            await message.channel.send(content=msg, embed=dashboard_embed)
            return

        # Prefix command: !movie_hangout, !hangout
        if content.startswith(("!movie_hangout", "!hangout")):
            if not message.guild:
                return
            success, msg = await self.scheduler_service.trigger_movie_hangout(message.guild)
            await message.channel.send(msg)
            return

        # Prefix command: !autonomous_sprint, !autonomous
        if content.startswith(("!autonomous_sprint", "!autonomous")):
            if not message.guild:
                return
            result = await self.run_autonomous_project_cycle(message.guild)
            if result:
                await message.channel.send(
                    f"🚀 **Autonomous Project Sprint Completed!**\n"
                    f"Prototype **{result['project']}** generated by **{result['team']}** and launched into #{result['channel']}!"
                )
            else:
                await message.channel.send("⚠️ Autonomous sprint skipped (client project currently in progress).")
            return

    async def send_help_message(self, channel: discord.abc.Messageable):
        help_text = (
            "🚀 **Welcome to Vaelkry Dev Labs Enterprise Operations!**\n\n"
            "**Operational & Shift Commands:**\n"
            "• `/start` (or `!start`): Start company operations & activate 24h IST shift scheduler.\n"
            "• `/stop` (or `!stop`): Pause operations & disconnect bots from voice.\n"
            "• `/status` (or `!status`): Generate live TTF Vasan status logs routed to #yogesh-chat.\n"
            "• `/reset_and_build_server` (or `!reset_and_build_server`): Build CEO Handwritten Blueprint.\n"
            "• `/sync_layout` (or `!sync_layout`): Enforce strict category hierarchy & clean duplicate voice channels.\n"
            "• `/delegate_task <domain> <task>` (or `!delegate_task`): Smart task routing to Team Vaasan or Team Vijay.\n"
            "• `/spawn_squad <team> <lead>` (or `!spawn_squad`): Dynamic squad scaling above Night Spend.\n"
            "• `/executive_dashboard` (or `!dashboard`): Dispatch executive audit dashboard to #managers-space & #yogesh-chat.\n"
            "• `/movie_hangout` (or `!movie_hangout`): Move 2-3 dev bots into The Hangout Zone for a movie party.\n"
            "• `/autonomous_sprint` (or `!autonomous_sprint`): Trigger AI-to-AI prototype launch in #the-launchpad.\n"
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
            "• `/watercooler` (or `!watercooler`): Post daily pantry snack special & workplace trivia.\n"
            "• `/night_chatter` (or `!nightchatter`): Late-Night Banter with 2-4 sneaky bots in #cafeteria during Night Spend.\n\n"
            "💬 **Real Discord Player Chat & Roasts:**\n"
            "• `/chat <character> <message>` (or `!chat`): Chat casually in Tanglish with Vijay, SK, Anirudh, Trisha, etc.\n"
            "• `/roast <target> [character]` (or `!roast`): Drop a savage Tanglish roast on a teammate or code.\n"
            "• `/banter [topic]` (or `!banter`): Launch a 4-line mini banter battle between community characters.\n"
            "• `/clash [topic]` (or `!clash`): Full Team Vasan vs Team Vijay witty roast battle.\n"
            "• Shortcuts: `!v <msg>`, `!sk <msg>`, `!ani <msg>`, `!trisha <msg>`, `!loki <msg>`.\n"
            "• Direct mentions: Tag any bot (`@TTF Vasan`, `@Pradeep`, `@SadieSink`, etc.) for an instant comeback!\n"
            "• Cafeteria chatter: Type in `#cafeteria` or ping `@everyone` for natural instant bot replies!\n\n"
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

        # Stop and cleanup voice engine
        orchestrator.voice_service.cleanup_all()

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
