"""
Vaelkry Dev Labs - Server Structure Builder Module
Handles complete server reset & rebuild based on the CEO Handwritten Blueprint,
as well as dynamic team category scaling and position management.
"""

import asyncio
import logging
import os
import random
import sys
from typing import Any, Dict, List, Optional, Tuple
import discord

# Ensure UTF-8 console output for Windows systems
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

logger = logging.getLogger("VaelkryDevLabs.ServerBuilder")

# The CEO Handwritten Blueprint Structure
BLUEPRINT_STRUCTURE: List[Dict[str, Any]] = [
    {
        "category": "Yogesh Space",
        "text_channels": ["yogesh-chat"],
        "voice_channels": ["CEO vc"],
    },
    {
        "category": "Circular",
        "text_channels": ["announcements", "greeting"],
        "voice_channels": [],
    },
    {
        "category": "Common Pantry",
        "text_channels": ["cafeteria", "the-launchpad", "control-room", "managers-space"],
        "voice_channels": [],
    },
    {
        "category": "Tech Cafe",
        "text_channels": [],
        "voice_channels": [
            "The Seven Slide",
            "Byte & Bit",
            "The Hive",
            "The Hangout Zone",
        ],
    },
    {
        "category": "Team Vaasan",
        "text_channels": ["working-chat", "team-chat"],
        "voice_channels": ["Working Vc 1", "Working Vc 2"],
    },
    {
        "category": "Team Vijay",
        "text_channels": ["working-chat", "team-chat"],
        "voice_channels": ["Working Vc 1", "Working Vc 2"],
    },
    {
        "category": "Team Messi",
        "text_channels": ["working-chat", "team-chat"],
        "voice_channels": ["Working Vc 1", "Working Vc 2"],
    },
    {
        "category": "Team Dhoni",
        "text_channels": ["working-chat", "team-chat"],
        "voice_channels": ["Working Vc 1", "Working Vc 2"],
    },
    {
        "category": "Night Spend",
        "text_channels": [],
        "voice_channels": ["Sleep Room 1", "Sleep Room 2", "Sleep Room 3"],
    },
    {
        "category": "Vaelkry logs",
        "text_channels": ["full-logs"],
        "voice_channels": [],
    },
]


# The Enterprise Corporate Role Hierarchy
ENTERPRISE_ROLES: List[Dict[str, Any]] = [
    {
        "name": "👑 CEO & Founder",
        "color": discord.Color.gold(),
        "hoist": True,
        "mentionable": True,
        "for_owner": True,
    },
    {
        "name": "👔 Executive Suite",
        "color": discord.Color.purple(),
        "hoist": True,
        "mentionable": True,
        "for_bots": ["sadie", "millie"],
    },
    {
        "name": "🧠 Principal Tech Lead",
        "color": discord.Color.blue(),
        "hoist": True,
        "mentionable": True,
        "for_bots": ["ttf_vasan", "pradeep"],
    },
    {
        "name": "🎨 UI/UX Design Lead",
        "color": discord.Color.magenta(),
        "hoist": True,
        "mentionable": True,
        "for_bots": ["mamitha"],
    },
    {
        "name": "⚙️ DevOps & SRE Lead",
        "color": discord.Color.green(),
        "hoist": True,
        "mentionable": True,
        "for_bots": ["kayadu"],
    },
    {
        "name": "🛡️ InfoSec & QA Lead",
        "color": discord.Color.orange(),
        "hoist": True,
        "mentionable": True,
        "for_bots": ["muthazhagi"],
    },
    # Team Vijay Corporate Roles
    {
        "name": "👑 Team Lead | Team Vijay",
        "color": discord.Color.dark_gold(),
        "hoist": True,
        "mentionable": True,
        "for_bots": ["vijay"],
    },
    {
        "name": "🎤 Entertainment & Timing Lead",
        "color": discord.Color.gold(),
        "hoist": True,
        "mentionable": True,
        "for_bots": ["sivakarthikeyan"],
    },
    {
        "name": "🎵 Audio & Vibe Architect",
        "color": discord.Color.blurple(),
        "hoist": True,
        "mentionable": True,
        "for_bots": ["anirudh"],
    },
    {
        "name": "💅 Creative & Brand Lead",
        "color": discord.Color.pink(),
        "hoist": True,
        "mentionable": True,
        "for_bots": ["trisha"],
    },
    {
        "name": "🎬 Action & Operations Lead",
        "color": discord.Color.dark_red(),
        "hoist": True,
        "mentionable": True,
        "for_bots": ["lokesh"],
    },
    {
        "name": "🔥 Team Vijay",
        "color": discord.Color.dark_orange(),
        "hoist": True,
        "mentionable": True,
        "for_bots": ["vijay", "sivakarthikeyan", "anirudh", "trisha", "lokesh"],
    },
    {
        "name": "⚡ Team Vasan",
        "color": discord.Color.blue(),
        "hoist": True,
        "mentionable": True,
        "for_bots": ["ttf_vasan", "pradeep", "mamitha", "kayadu", "muthazhagi"],
    },
    # Team Messi Corporate Roles
    {
        "name": "👑 Team Lead | Team Messi",
        "color": discord.Color.from_rgb(0, 168, 255),
        "hoist": True,
        "mentionable": True,
        "for_bots": ["messi"],
    },
    {
        "name": "🔥 SIUUU & Code Performance Lead",
        "color": discord.Color.from_rgb(255, 75, 43),
        "hoist": True,
        "mentionable": True,
        "for_bots": ["ronaldo"],
    },
    {
        "name": "🕺 Motion Dynamics & UI Lead",
        "color": discord.Color.from_rgb(255, 215, 0),
        "hoist": True,
        "mentionable": True,
        "for_bots": ["neymar"],
    },
    {
        "name": "🤖 Brute-Force Data Cruncher Lead",
        "color": discord.Color.from_rgb(108, 92, 231),
        "hoist": True,
        "mentionable": True,
        "for_bots": ["haaland"],
    },
    {
        "name": "⚡ Edge Routing & CDN Architect",
        "color": discord.Color.from_rgb(0, 206, 201),
        "hoist": True,
        "mentionable": True,
        "for_bots": ["mbappe"],
    },
    {
        "name": "⚽ Team Messi",
        "color": discord.Color.from_rgb(0, 150, 255),
        "hoist": True,
        "mentionable": True,
        "for_bots": ["messi", "ronaldo", "neymar", "haaland", "mbappe"],
    },
    # Team Dhoni Corporate Roles
    {
        "name": "👑 Team Lead | Team Dhoni",
        "color": discord.Color.from_rgb(255, 204, 0),
        "hoist": True,
        "mentionable": True,
        "for_bots": ["dhoni"],
    },
    {
        "name": "🦁 Aggressive Review & Standards Lead",
        "color": discord.Color.from_rgb(231, 76, 60),
        "hoist": True,
        "mentionable": True,
        "for_bots": ["virat"],
    },
    {
        "name": "🍔 Core Architecture & Stability Lead",
        "color": discord.Color.from_rgb(52, 152, 219),
        "hoist": True,
        "mentionable": True,
        "for_bots": ["rohit"],
    },
    {
        "name": "⚔️ Defensive Security & Leak Hunter",
        "color": discord.Color.from_rgb(46, 204, 113),
        "hoist": True,
        "mentionable": True,
        "for_bots": ["jadeja"],
    },
    {
        "name": "🕶️ Hotfix & High-Swagger All-Rounder",
        "color": discord.Color.from_rgb(155, 89, 182),
        "hoist": True,
        "mentionable": True,
        "for_bots": ["hardik"],
    },
    {
        "name": "🏏 Team Dhoni",
        "color": discord.Color.from_rgb(241, 196, 15),
        "hoist": True,
        "mentionable": True,
        "for_bots": ["dhoni", "virat", "rohit", "jadeja", "hardik"],
    },
    {
        "name": "💻 Software Engineer",
        "color": discord.Color.teal(),
        "hoist": True,
        "mentionable": True,
        "for_humans": True,
    },
    {
        "name": "🎓 Engineering Intern",
        "color": discord.Color.light_grey(),
        "hoist": False,
        "mentionable": False,
    },
]


async def ensure_enterprise_roles(
    guild: discord.Guild,
    clients: Optional[Dict[str, Any]] = None,
) -> Dict[str, discord.Role]:
    """
    Provisions and configures all official enterprise roles in the guild:
    - Creates missing roles with dedicated corporate colors and hoists.
    - Assigns '👑 CEO & Founder' to the server owner / Yogesh.
    - Assigns departmental lead roles to the respective bots.
    - Assigns '💻 Software Engineer' to human developers.
    """
    created_roles: Dict[str, discord.Role] = {}

    for cfg in ENTERPRISE_ROLES:
        role_name = cfg["name"]
        existing_role = discord.utils.find(
            lambda r: r.name.lower() == role_name.lower() or cfg["name"].split()[1].lower() in r.name.lower(),
            guild.roles,
        )

        if not existing_role:
            try:
                existing_role = await guild.create_role(
                    name=role_name,
                    color=cfg["color"],
                    hoist=cfg.get("hoist", True),
                    mentionable=cfg.get("mentionable", True),
                    reason="Vaelkry Dev Labs Enterprise Role Provisioning",
                )
                logger.info(f"Created enterprise role '{role_name}' in guild '{guild.name}'.")
            except Exception as exc:
                logger.warning(f"Could not create role '{role_name}': {exc}")
                continue

        created_roles[role_name] = existing_role

    # 1. Assign CEO & Founder to Guild Owner
    ceo_role = created_roles.get("👑 CEO & Founder")
    owner = guild.owner or guild.get_member(guild.owner_id)
    if ceo_role and owner:
        if ceo_role not in owner.roles:
            try:
                await owner.add_roles(ceo_role, reason="Founder / CEO Provisioning")
                logger.info(f"Assigned '{ceo_role.name}' to Owner '{owner.display_name}'.")
            except Exception as exc:
                logger.warning(f"Failed to assign CEO role to owner: {exc}")

    # 2. Assign specialized lead roles to bots
    if clients:
        for cfg in ENTERPRISE_ROLES:
            bot_keys = cfg.get("for_bots")
            if not bot_keys:
                continue
            role = created_roles.get(cfg["name"])
            if not role:
                continue

            for bot_key in bot_keys:
                client = clients.get(bot_key)
                if client and client.user:
                    bot_member = guild.get_member(client.user.id)
                    if bot_member and role not in bot_member.roles:
                        try:
                            await bot_member.add_roles(role, reason=f"Corporate Bot Role: {role.name}")
                            logger.info(f"Assigned '{role.name}' to Bot '{bot_member.name}'.")
                        except Exception as exc:
                            logger.warning(f"Failed to assign '{role.name}' to bot {bot_key}: {exc}")

    # 3. Assign Software Engineer to human members without developer roles
    se_role = created_roles.get("💻 Software Engineer")
    if se_role:
        for member in guild.members:
            if not member.bot and member.id != guild.owner_id:
                has_dev_role = any(r.name in created_roles for r in member.roles)
                if not has_dev_role and se_role not in member.roles:
                    try:
                        await member.add_roles(se_role, reason="Employee Onboarding")
                        logger.info(f"Assigned '{se_role.name}' to member '{member.display_name}'.")
                    except Exception as exc:
                        logger.warning(f"Failed to assign '{se_role.name}' to {member.display_name}: {exc}")

    # 4. Ensure all squad categories and channels exist and adhere to 4-tier hierarchy
    try:
        await sync_server_category_layout(guild)
    except Exception as exc:
        logger.warning(f"Could not auto-ensure squad categories: {exc}")

    return created_roles


_team_vijay_lock = asyncio.Lock()


async def sync_server_category_layout(
    guild: discord.Guild,
) -> List[discord.CategoryChannel]:
    """
    Enforces the strict corporate category hierarchy on Discord:
    Strict Category Hierarchy from Bottom to Top:
    1. Absolute Last Category (bottom of server): 'Vaelkry logs'
    2. Second from Bottom (directly above 'Vaelkry logs'): 'Night Spend'
    3. Above 'Night Spend': All team categories ('Team Vaasan', 'Team Vijay', and future teams)
    4. Top of server: Executive & Tech Cafe categories ('Yogesh Space', 'Circular', 'Common Pantry', 'Tech Cafe')

    Implementation details:
    - Explicitly updates category positions in Discord so that:
      * Team categories have lower position indices than 'Night Spend'.
      * 'Night Spend' sits right below all team categories.
      * 'Vaelkry logs' sits at the very bottom.
    - Under 'Team Vijay', finds and deletes duplicate 'Working Vc 2' voice channels
      so that only one 'Working Vc 1' and one 'Working Vc 2' remain.
    """
    async with _team_vijay_lock:
        return await _sync_server_category_layout_internal(guild)


async def _sync_server_category_layout_internal(
    guild: discord.Guild,
) -> List[discord.CategoryChannel]:
    """
    Internal implementation to enforce category ordering and channel cleanup.
    Provisions and cleans all 4 squads (Team Vaasan, Team Vijay, Team Messi, Team Dhoni),
    removes duplicate voice channels (strictly 1 Working Vc 1, 1 Working Vc 2),
    removes duplicate text channels (strictly 1 working-chat, 1 team-chat),
    and enforces the strict 4-Tier Layout Hierarchy.
    """
    # 0. Ensure guild channels/categories are populated in cache
    if not guild.categories:
        try:
            await guild.fetch_channels()
        except Exception:
            pass

    expected_vc_names = ["Working Vc 1", "Working Vc 2"]
    expected_text_names = ["working-chat", "team-chat"]

    def classify_vc(vc_name: str) -> Optional[str]:
        cleaned = " ".join(vc_name.strip().lower().replace("-", " ").replace("_", " ").split())
        if "1" in cleaned and ("working" in cleaned or "vc" in cleaned):
            return "Working Vc 1"
        if "2" in cleaned and ("working" in cleaned or "vc" in cleaned):
            return "Working Vc 2"
        return None

    # 1. Ensure all 4 squad categories exist and have strictly 2 text & 2 voice channels
    standard_squads = ["Team Vaasan", "Team Vijay", "Team Messi", "Team Dhoni"]
    for squad_name in standard_squads:
        cat_squad = discord.utils.find(
            lambda c, s=squad_name: c.name.strip().lower() == s.lower()
            or (s.lower() == "team vaasan" and c.name.strip().lower() == "team vasan"),
            guild.categories,
        )
        if not cat_squad:
            cat_squad = await guild.create_category(name=squad_name)
            logger.info(f"Provisioned missing category '{squad_name}' in {guild.name}")

        # Cleanup & provision voice channels
        kept_voice_channels: Dict[str, discord.VoiceChannel] = {}
        cat_vcs = [vc for vc in guild.voice_channels if vc.category_id == cat_squad.id]
        if not cat_vcs:
            cat_vcs = list(cat_squad.voice_channels)

        for vc in cat_vcs:
            matched_target = classify_vc(vc.name)
            if matched_target in expected_vc_names:
                if matched_target not in kept_voice_channels:
                    kept_voice_channels[matched_target] = vc
                    if vc.name != matched_target:
                        try:
                            await vc.edit(name=matched_target)
                        except Exception:
                            pass
                else:
                    # Duplicate voice channel found -> Delete it!
                    try:
                        logger.info(f"Deleting duplicate voice channel '{vc.name}' (ID: {vc.id}) under '{cat_squad.name}'")
                        await vc.delete(reason=f"Cleanup duplicate Working Vc in {squad_name}")
                    except Exception as del_exc:
                        logger.warning(f"Failed to delete duplicate voice channel {vc.name}: {del_exc}")
            else:
                try:
                    logger.info(f"Deleting extraneous voice channel '{vc.name}' (ID: {vc.id}) under '{cat_squad.name}'")
                    await vc.delete(reason=f"Keep strictly Working Vc 1 and Working Vc 2 in {squad_name}")
                except Exception as del_exc:
                    logger.warning(f"Failed to delete extraneous voice channel {vc.name}: {del_exc}")

        for vc_name in expected_vc_names:
            if vc_name not in kept_voice_channels:
                try:
                    new_vc = await cat_squad.create_voice_channel(name=vc_name)
                    logger.info(f"Created missing voice channel '{vc_name}' under {squad_name}")
                    kept_voice_channels[vc_name] = new_vc
                except Exception as create_exc:
                    logger.error(f"Failed to create voice channel '{vc_name}': {create_exc}")

        # Cleanup & provision text channels
        kept_text_channels: Dict[str, discord.TextChannel] = {}
        cat_tcs = [tc for tc in guild.text_channels if tc.category_id == cat_squad.id]
        if not cat_tcs:
            cat_tcs = list(cat_squad.text_channels)

        for tc in cat_tcs:
            norm_name = tc.name.strip().lower()
            matched_expected = next((name for name in expected_text_names if name.lower() == norm_name), None)
            if matched_expected:
                if matched_expected not in kept_text_channels:
                    kept_text_channels[matched_expected] = tc
                else:
                    try:
                        logger.info(f"Deleting duplicate text channel '#{tc.name}' (ID: {tc.id}) under '{cat_squad.name}'")
                        await tc.delete(reason=f"Cleanup duplicate text channel in {squad_name}")
                    except Exception as del_exc:
                        logger.warning(f"Failed to delete duplicate text channel #{tc.name}: {del_exc}")
            else:
                try:
                    logger.info(f"Deleting extraneous text channel '#{tc.name}' (ID: {tc.id}) under '{cat_squad.name}'")
                    await tc.delete(reason=f"Keep strictly working-chat and team-chat in {squad_name}")
                except Exception as del_exc:
                    logger.warning(f"Failed to delete extraneous text channel #{tc.name}: {del_exc}")

        for tc_name in expected_text_names:
            if tc_name not in kept_text_channels:
                try:
                    new_tc = await cat_squad.create_text_channel(name=tc_name)
                    logger.info(f"Created missing text channel #{tc_name} under {squad_name}")
                    kept_text_channels[tc_name] = new_tc
                except Exception as create_exc:
                    logger.error(f"Failed to create text channel #{tc_name}: {create_exc}")

    # 2. Discover or ensure 'Night Spend' and 'Vaelkry logs' categories
    night_spend_cat = discord.utils.find(
        lambda c: c.name.strip().lower() == "night spend",
        guild.categories,
    )
    if not night_spend_cat:
        night_spend_cat = await guild.create_category(name="Night Spend")
        logger.info(f"Provisioned missing category 'Night Spend' in {guild.name}")

    logs_cat = discord.utils.find(
        lambda c: "log" in c.name.strip().lower(),
        guild.categories,
    )
    if not logs_cat:
        logs_cat = await guild.create_category(name="Vaelkry logs")
        logger.info(f"Provisioned missing category 'Vaelkry logs' in {guild.name}")

    # 3. Partition categories into the strict 4-tier layout hierarchy:
    # Tier 1 (Top of Server): Executive & Tech Cafe categories
    # Tier 2: Squads ('Team Vaasan', 'Team Vijay', 'Team Messi', 'Team Dhoni')
    # Tier 3 (Second from Bottom): 'Night Spend' (Sleep Room 1, 2, 3)
    # Tier 4 (Absolute Last Category): 'Vaelkry logs' (#full-logs at absolute bottom)
    top_categories: List[discord.CategoryChannel] = []
    team_categories: List[discord.CategoryChannel] = []

    for c in list(guild.categories):
        c_name = c.name.strip().lower()
        if c.id == logs_cat.id or "log" in c_name:
            continue
        elif c.id == night_spend_cat.id or c_name == "night spend":
            continue
        elif c_name.startswith("team") or c_name in ("team vaasan", "team vasan", "team vijay", "team messi", "team dhoni"):
            team_categories.append(c)
        else:
            top_categories.append(c)

    # Sort Tier 1: Blueprint top order
    blueprint_top_order = ["yogesh space", "circular", "common pantry", "tech cafe"]
    def top_cat_sort_key(c: discord.CategoryChannel) -> int:
        c_name = c.name.strip().lower()
        for idx, bp in enumerate(blueprint_top_order):
            if bp in c_name:
                return idx
        return len(blueprint_top_order) + getattr(c, "position", 0)

    top_categories.sort(key=top_cat_sort_key)

    # Sort Tier 2: Team Vaasan -> Team Vijay -> Team Messi -> Team Dhoni -> any extra teams
    def team_cat_sort_key(c: discord.CategoryChannel) -> int:
        c_name = c.name.strip().lower()
        if c_name in ("team vaasan", "team vasan"):
            return 0
        if c_name == "team vijay":
            return 1
        if c_name == "team messi":
            return 2
        if c_name == "team dhoni":
            return 3
        return 10 + getattr(c, "position", 0)

    team_categories.sort(key=team_cat_sort_key)

    # 4. Assemble the final strict order
    ordered_categories: List[discord.CategoryChannel] = []
    seen_ids = set()
    for cat in top_categories + team_categories + [night_spend_cat] + [logs_cat]:
        if cat and cat.id not in seen_ids:
            seen_ids.add(cat.id)
            ordered_categories.append(cat)

    # 5. Explicitly update category positions in Discord
    payload = [{"id": c.id, "position": idx} for idx, c in enumerate(ordered_categories)]

    try:
        if hasattr(guild, "_state") and hasattr(guild._state, "http"):
            await guild._state.http.bulk_channel_update(
                guild.id,
                payload,
                reason="Strict Category Layout Hierarchy (CEO Blueprint)",
            )
            for idx, c in enumerate(ordered_categories):
                c.position = idx
            logger.info(
                f"Successfully updated atomic category layout in {guild.name}: "
                f"{[f'{c.name} (pos {idx})' for idx, c in enumerate(ordered_categories)]}"
            )
    except Exception as bulk_exc:
        logger.warning(f"bulk_channel_update failed ({bulk_exc}). Falling back to category.edit...")
        for idx, c in enumerate(ordered_categories):
            try:
                await c.edit(position=idx)
            except Exception as e:
                logger.warning(f"Failed to edit position for {c.name}: {e}")

    return ordered_categories


async def ensure_team_vijay_category(
    guild: discord.Guild,
) -> Tuple[discord.CategoryChannel, List[discord.abc.GuildChannel]]:
    """
    Ensures that the dedicated category 'Team Vijay' exists on Discord with:
    - Text channels: strictly 'working-chat', 'team-chat' (cleans up any duplicates)
    - Voice channels: strictly 'Working Vc 1', 'Working Vc 2' (cleans up duplicate 'Working Vc 2')
    - Positioned strictly ABOVE 'Night Spend' and immediately below 'Team Vaasan'.
    """
    async with _team_vijay_lock:
        ordered_cats = await _sync_server_category_layout_internal(guild)
        cat = discord.utils.find(lambda c: c.name.strip().lower() == "team vijay", ordered_cats or guild.categories)
        channels = list(getattr(cat, "channels", None) or (list(getattr(cat, "text_channels", [])) + list(getattr(cat, "voice_channels", [])))) if cat else []
        return cat, channels


async def ensure_team_category(
    guild: discord.Guild,
    team_name: str,
) -> Tuple[Optional[discord.CategoryChannel], List[discord.abc.GuildChannel]]:
    """
    Ensures that a specified squad category (e.g. 'Team Messi', 'Team Dhoni') exists
    with its required text and voice channels, positioned in Tier 2 above 'Night Spend'.
    """
    clean_target = team_name.strip().lower()
    async with _team_vijay_lock:
        ordered_cats = await _sync_server_category_layout_internal(guild)
        cat = discord.utils.find(
            lambda c: c.name.strip().lower() == clean_target
            or c.name.strip().lower() == f"team {clean_target}",
            ordered_cats or guild.categories,
        )
        channels = list(getattr(cat, "channels", None) or (list(getattr(cat, "text_channels", [])) + list(getattr(cat, "voice_channels", [])))) if cat else []
        return cat, channels



def is_admin_or_owner(member: discord.Member, guild: discord.Guild) -> bool:
    """Checks if the member is the server owner or an administrator."""
    if member == guild.owner or member.id == guild.owner_id:
        return True
    perms = getattr(member, "guild_permissions", None)
    if perms and (perms.administrator or perms.manage_guild):
        return True
    return False


def update_env_project_channel(new_id: int):
    """Persists the updated project channel ID into the local .env file."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(env_path):
        logger.warning(f".env file not found at {env_path}. Skipping file persistence.")
        return

    try:
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        updated = False
        new_lines = []
        for line in lines:
            if line.strip().startswith("PROJECT_CHANNEL_ID="):
                new_lines.append(f"PROJECT_CHANNEL_ID={new_id}\n")
                updated = True
            else:
                new_lines.append(line)

        if not updated:
            new_lines.append(f"\nPROJECT_CHANNEL_ID={new_id}\n")

        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

        logger.info(f"Successfully persisted PROJECT_CHANNEL_ID={new_id} to {env_path}")
    except Exception as exc:
        logger.error(f"Failed to update .env with new project channel ID: {exc}")


async def reset_and_build_server(
    guild: discord.Guild,
    send_fn,
) -> Tuple[Dict[str, List[discord.abc.GuildChannel]], Optional[discord.TextChannel]]:
    """
    Deletes all existing channels & categories and strictly builds the CEO Blueprint.
    Returns (hierarchy, launchpad_channel).
    """
    initial_hype = (
        "⚠️ **Vaelkry Dev Labs — Full Infrastructure Reset Initiated!** 🏢⚡\n"
        "🏍️💨 *TTF Vasan & Squad in full action:* Resetting all channels and strictly deploying "
        "the **CEO Handwritten Blueprint** at 299 km/h speed!\n"
        "*(Building Yogesh Space, Circular, Common Pantry, Tech Cafe, Team Vaasan, and Vaelkry logs...)*"
    )
    try:
        await send_fn(initial_hype)
    except Exception as exc:
        logger.warning(f"Could not send initial message: {exc}")

    # Record all existing channels prior to blueprint creation
    old_channels = list(guild.channels)
    new_channel_ids = set()
    hierarchy: Dict[str, List[discord.abc.GuildChannel]] = {}
    launchpad_channel: Optional[discord.TextChannel] = None

    # Step 1: Create the Blueprint Categories & Channels
    for pos_index, section in enumerate(BLUEPRINT_STRUCTURE):
        cat_name = section["category"]
        text_names: List[str] = section["text_channels"]
        voice_names: List[str] = section["voice_channels"]

        category = await guild.create_category(name=cat_name, position=pos_index)
        new_channel_ids.add(category.id)
        hierarchy[cat_name] = []

        # Create text channels
        for t_name in text_names:
            t_clean = t_name.strip().lower()
            text_ch = await category.create_text_channel(name=t_clean)
            new_channel_ids.add(text_ch.id)
            hierarchy[cat_name].append(text_ch)
            if t_clean in ("the-launchpad", "working-chat"):
                if launchpad_channel is None or t_clean == "the-launchpad":
                    launchpad_channel = text_ch

        # Create voice channels
        for v_name in voice_names:
            v_clean = v_name.strip()
            voice_ch = await category.create_voice_channel(name=v_clean)
            new_channel_ids.add(voice_ch.id)
            hierarchy[cat_name].append(voice_ch)

    # Step 2: Delete old channels/categories that were not part of the newly created set
    logger.info(f"Purging {len(old_channels)} old channels/categories...")
    for old_ch in old_channels:
        if old_ch.id not in new_channel_ids:
            try:
                await old_ch.delete(reason="CEO Server Structure Reset & Rebuild")
            except Exception as exc:
                logger.warning(f"Could not delete old channel {old_ch.name}: {exc}")

    # Step 3: Update PROJECT_CHANNEL_ID in memory and .env
    if launchpad_channel:
        update_env_project_channel(launchpad_channel.id)

    return hierarchy, launchpad_channel


async def create_dynamic_team_category(
    guild: discord.Guild,
    team_name: str,
) -> Tuple[discord.CategoryChannel, List[discord.abc.GuildChannel]]:
    """
    Duplicates the 'Team Vaasan' template for a new team:
    Category: "Team {team_name}"
    Text: "working-chat", "team-chat"
    Voice: "Working Vc 1", "Working Vc 2"
    Positions it strictly right below 'Team Vaasan' and before 'Vaelkry logs'.
    """
    clean_team_title = team_name.strip().title()
    category_name = f"Team {clean_team_title}"

    # Check if category already exists
    existing = discord.utils.get(guild.categories, name=category_name)
    if existing:
        return existing, list(existing.channels)

    # Determine positioning: strictly right above 'Night Spend' and below 'Team Vaasan'
    night_spend_cat = discord.utils.find(lambda c: c.name.strip().lower() == "night spend", guild.categories)
    vaasan_cat = discord.utils.find(lambda c: c.name.strip().lower() in ("team vaasan", "team vasan"), guild.categories)
    logs_cat = discord.utils.find(lambda c: "log" in c.name.strip().lower(), guild.categories)

    target_position = None
    if night_spend_cat:
        target_position = night_spend_cat.position
    elif vaasan_cat:
        target_position = vaasan_cat.position + 1

    # Create new category
    if target_position is not None:
        category = await guild.create_category(name=category_name, position=target_position)
    else:
        category = await guild.create_category(name=category_name)

    created_channels: List[discord.abc.GuildChannel] = []

    # Text channels
    t1 = await category.create_text_channel(name="working-chat")
    t2 = await category.create_text_channel(name="team-chat")
    created_channels.extend([t1, t2])

    # Voice channels
    v1 = await category.create_voice_channel(name="Working Vc 1")
    v2 = await category.create_voice_channel(name="Working Vc 2")
    created_channels.extend([v1, v2])

    # Strictly sync and enforce category hierarchy (Executive -> Teams -> Night Spend -> Logs)
    try:
        await sync_server_category_layout(guild)
    except Exception as sync_exc:
        logger.warning(f"Failed to auto-sync category layout after creating team {team_name}: {sync_exc}")

    return category, created_channels


async def spawn_new_squad(
    guild: discord.Guild,
    team_name: str,
    lead_name: str,
) -> Tuple[discord.CategoryChannel, List[discord.abc.GuildChannel], discord.Role]:
    """
    Dynamically scales and provisions a new engineering squad:
    1. Provisions a dedicated category (e.g. 'Team Falcon').
    2. Provisions text channels: 'working-chat', 'team-chat'.
    3. Provisions voice channels: 'Working Vc 1', 'Working Vc 2'.
    4. Provisions a distinctive team role: '⚡ Team <Name>' with color.
    5. Strictly synchronizes category layout so the new team is placed
       in Tier 2 directly ABOVE 'Night Spend'.
    """
    clean_name = team_name.strip()
    category_title = clean_name if clean_name.lower().startswith("team") else f"Team {clean_name.title()}"
    role_title = f"⚡ {category_title}"

    # 1. Provision Role
    existing_role = discord.utils.find(lambda r: r.name.lower() == role_title.lower(), guild.roles)
    if not existing_role:
        vibrant_colors = [
            discord.Color.from_rgb(0, 210, 255),
            discord.Color.from_rgb(255, 0, 128),
            discord.Color.from_rgb(0, 255, 128),
            discord.Color.from_rgb(255, 170, 0),
            discord.Color.from_rgb(170, 0, 255),
        ]
        team_role = await guild.create_role(
            name=role_title,
            color=random.choice(vibrant_colors),
            mentionable=True,
            reason=f"Spawn Squad: {category_title} led by {lead_name}",
        )
    else:
        team_role = existing_role

    # 2. Provision Category
    existing_cat = discord.utils.find(lambda c: c.name.strip().lower() == category_title.lower(), guild.categories)
    if not existing_cat:
        category = await guild.create_category(name=category_title)
    else:
        category = existing_cat

    created_channels: List[discord.abc.GuildChannel] = []

    # 3. Channels: text: working-chat, team-chat; voice: Working Vc 1, Working Vc 2
    for tc_name in ["working-chat", "team-chat"]:
        existing_tc = discord.utils.find(
            lambda c: c.name.lower() == tc_name and c.category_id == category.id,
            guild.text_channels,
        )
        if not existing_tc:
            new_tc = await category.create_text_channel(name=tc_name)
            created_channels.append(new_tc)
        else:
            created_channels.append(existing_tc)

    for vc_name in ["Working Vc 1", "Working Vc 2"]:
        existing_vc = discord.utils.find(
            lambda c: c.name.lower() == vc_name.lower() and c.category_id == category.id,
            guild.voice_channels,
        )
        if not existing_vc:
            new_vc = await category.create_voice_channel(name=vc_name)
            created_channels.append(new_vc)
        else:
            created_channels.append(existing_vc)

    # 4. Strictly synchronize category layout so the new team is placed in Tier 2 above 'Night Spend'
    await sync_server_category_layout(guild)

    return category, created_channels, team_role


def format_blueprint_directory(
    hierarchy: Dict[str, List[discord.abc.GuildChannel]],
    launchpad: Optional[discord.TextChannel],
) -> str:
    """Formats the comprehensive directory listing of the CEO blueprint."""
    lines = [
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "🏁 **VAELKRY DEV LABS — CEO BLUEPRINT DEPLOYED!** 🏢⚡",
        "The server structure has been reset and strictly configured to the CEO Handwritten Blueprint!",
        "",
        "📁 **Official Department Directory:**",
    ]

    for cat_name, channels in hierarchy.items():
        lines.append(f"\n📂 **{cat_name}**")
        for ch in channels:
            if isinstance(ch, discord.TextChannel):
                if launchpad and ch.id == launchpad.id:
                    lines.append(f"  • {ch.mention} 🚀 **(Active Project Launchpad)**")
                elif ch.name == "full-logs":
                    lines.append(f"  • {ch.mention} 🛡️ *(Executive Audit Log)*")
                elif ch.name == "greeting":
                    lines.append(f"  • {ch.mention} 🌟 *(Visitor & Member Onboarding)*")
                else:
                    lines.append(f"  • {ch.mention}")
            elif isinstance(ch, discord.VoiceChannel):
                lines.append(f"  • 🔊 `{ch.name}` *(Voice Channel)*")

    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    if launchpad:
        lines.append(
            f"🎯 **Project Command Center:**\n"
            f"Run `!project <tech idea>` directly inside {launchpad.mention} or any team's `#working-chat`! 🔥"
        )
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    return "\n".join(lines)
