"""
Vaelkry Dev Labs - Server Structure Builder Module
Handles complete server reset & rebuild based on the CEO Handwritten Blueprint,
as well as dynamic team category scaling and position management.
"""

import asyncio
import logging
import os
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

    # 4. Ensure Team Vijay category and channels exist
    try:
        await ensure_team_vijay_category(guild)
    except Exception as exc:
        logger.warning(f"Could not auto-ensure Team Vijay category: {exc}")

    return created_roles


_team_vijay_lock = asyncio.Lock()


async def ensure_team_vijay_category(
    guild: discord.Guild,
) -> Tuple[discord.CategoryChannel, List[discord.abc.GuildChannel]]:
    """
    Thread-safe / task-safe wrapper to ensure Team Vijay category and channels exist.
    """
    async with _team_vijay_lock:
        return await _ensure_team_vijay_category_internal(guild)


async def _ensure_team_vijay_category_internal(
    guild: discord.Guild,
) -> Tuple[discord.CategoryChannel, List[discord.abc.GuildChannel]]:
    """
    Ensures that the dedicated category 'Team Vijay' exists on Discord with:
    - Text channels: strictly 'working-chat', 'team-chat' (cleans up any duplicates)
    - Voice channels: strictly 'Working Vc 1', 'Working Vc 2' (cleans up any duplicates, e.g. duplicate 'Working Vc 2')
    - Positioned strictly ABOVE 'Night Spend' and immediately below 'Team Vaasan'.
    """
    cat = discord.utils.find(
        lambda c: c.name.strip().lower() == "team vijay",
        guild.categories,
    )

    # 1. Discover surrounding categories to enforce strict layout:
    # Team Vaasan -> Team Vijay -> Night Spend -> Vaelkry logs
    night_spend_cat = discord.utils.find(
        lambda c: c.name.strip().lower() == "night spend",
        guild.categories,
    )
    vasan_cat = discord.utils.find(
        lambda c: c.name.strip().lower() in ("team vaasan", "team vasan"),
        guild.categories,
    )
    logs_cat = discord.utils.find(
        lambda c: "log" in c.name.strip().lower(),
        guild.categories,
    )

    # Target position: immediately above Night Spend (below Team Vaasan)
    target_pos = None
    if night_spend_cat:
        target_pos = night_spend_cat.position
    elif vasan_cat:
        target_pos = vasan_cat.position + 1

    if not cat:
        if target_pos is not None:
            cat = await guild.create_category(name="Team Vijay", position=target_pos)
        else:
            cat = await guild.create_category(name="Team Vijay")
        logger.info(f"Provisioned new category 'Team Vijay' at position {cat.position} in {guild.name}")

    # Enforce strict category ordering:
    # 1. Ensure all team categories (e.g. 'Team Vaasan', 'Team Vijay') are strictly positioned ABOVE 'Night Spend'.
    # 2. Fetch the position of 'Night Spend'. Set the position of 'Team Vijay' so it appears immediately above 'Night Spend' (below 'Team Vaasan').
    try:
        if night_spend_cat:
            # Step A: Ensure Team Vaasan and any other team categories are strictly positioned ABOVE 'Night Spend'
            if vasan_cat and vasan_cat.position >= night_spend_cat.position:
                await vasan_cat.edit(position=max(0, night_spend_cat.position - 1))

            for other_team in list(guild.categories):
                if other_team.id not in (cat.id, (vasan_cat.id if vasan_cat else None)):
                    if other_team.name.strip().lower().startswith("team") and other_team.position >= night_spend_cat.position:
                        await other_team.edit(position=max(0, night_spend_cat.position - 1))

            # Step B: Fetch the position of 'Night Spend'. Set the position of 'Team Vijay' so it appears immediately above 'Night Spend' (below 'Team Vaasan')
            night_spend_pos = night_spend_cat.position
            desired_vijay_pos = night_spend_pos
            if vasan_cat and desired_vijay_pos <= vasan_cat.position:
                desired_vijay_pos = vasan_cat.position + 1

            await cat.edit(position=desired_vijay_pos)

            # Step C: Ensure Night Spend is positioned strictly below Team Vijay
            if night_spend_cat.position <= cat.position:
                await night_spend_cat.edit(position=cat.position + 1)
        elif vasan_cat:
            await cat.edit(position=vasan_cat.position + 1)

        # Keep logs at the bottom
        if logs_cat:
            await logs_cat.edit(position=len(guild.categories) + 5)
    except Exception as pos_exc:
        logger.warning(f"Failed to adjust category ordering for Team Vijay: {pos_exc}")

    # 2. Clean up duplicate voice channels & ensure strictly 'Working Vc 1' and 'Working Vc 2'
    expected_vc_names = ["Working Vc 1", "Working Vc 2"]
    kept_voice_channels: Dict[str, discord.VoiceChannel] = {}

    def classify_vc(vc_name: str) -> Optional[str]:
        cleaned = " ".join(vc_name.strip().lower().replace("-", " ").replace("_", " ").split())
        if "1" in cleaned and ("working" in cleaned or "vc" in cleaned):
            return "Working Vc 1"
        if "2" in cleaned and ("working" in cleaned or "vc" in cleaned):
            return "Working Vc 2"
        return None

    # Retrieve all voice channels belonging to Team Vijay (both from category and guild cache)
    cat_vcs = [vc for vc in guild.voice_channels if vc.category_id == cat.id]
    if not cat_vcs:
        cat_vcs = list(cat.voice_channels)

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
                # Duplicate voice channel found (e.g. extra 'Working Vc 2') -> Delete it!
                try:
                    logger.info(f"Deleting duplicate voice channel '{vc.name}' (ID: {vc.id}) under '{cat.name}'")
                    await vc.delete(reason="Cleanup duplicate voice channel in Team Vijay")
                except Exception as del_exc:
                    logger.warning(f"Failed to delete duplicate voice channel {vc.name}: {del_exc}")
        else:
            # Extraneous voice channel under Team Vijay -> delete to keep strictly Working Vc 1 and Working Vc 2
            try:
                logger.info(f"Deleting extraneous voice channel '{vc.name}' (ID: {vc.id}) under '{cat.name}'")
                await vc.delete(reason="Keep strictly Working Vc 1 and Working Vc 2 in Team Vijay")
            except Exception as del_exc:
                logger.warning(f"Failed to delete extraneous voice channel {vc.name}: {del_exc}")

    # Ensure missing voice channels are created
    for vc_name in expected_vc_names:
        if vc_name not in kept_voice_channels:
            try:
                new_vc = await cat.create_voice_channel(name=vc_name)
                logger.info(f"Created missing voice channel '{vc_name}' under Team Vijay")
                kept_voice_channels[vc_name] = new_vc
            except Exception as create_exc:
                logger.error(f"Failed to create voice channel '{vc_name}': {create_exc}")

    # 3. Clean up duplicate text channels & ensure strictly 'working-chat', 'team-chat'
    expected_text_names = ["working-chat", "team-chat"]
    kept_text_channels: Dict[str, discord.TextChannel] = {}

    cat_tcs = [tc for tc in guild.text_channels if tc.category_id == cat.id]
    if not cat_tcs:
        cat_tcs = list(cat.text_channels)

    for tc in cat_tcs:
        norm_name = tc.name.strip().lower()
        matched_expected = next((name for name in expected_text_names if name.lower() == norm_name), None)
        if matched_expected:
            if matched_expected not in kept_text_channels:
                kept_text_channels[matched_expected] = tc
            else:
                # Duplicate text channel found -> Delete it!
                try:
                    logger.info(f"Deleting duplicate text channel '#{tc.name}' (ID: {tc.id}) under '{cat.name}'")
                    await tc.delete(reason="Cleanup duplicate text channel in Team Vijay")
                except Exception as del_exc:
                    logger.warning(f"Failed to delete duplicate text channel #{tc.name}: {del_exc}")
        else:
            try:
                logger.info(f"Deleting extraneous text channel '#{tc.name}' (ID: {tc.id}) under '{cat.name}'")
                await tc.delete(reason="Keep strictly working-chat and team-chat in Team Vijay")
            except Exception as del_exc:
                logger.warning(f"Failed to delete extraneous text channel #{tc.name}: {del_exc}")

    # Ensure missing text channels are created
    for tc_name in expected_text_names:
        if tc_name not in kept_text_channels:
            try:
                new_tc = await cat.create_text_channel(name=tc_name)
                logger.info(f"Created missing text channel #{tc_name} under Team Vijay")
                kept_text_channels[tc_name] = new_tc
            except Exception as create_exc:
                logger.error(f"Failed to create text channel #{tc_name}: {create_exc}")

    channels: List[discord.abc.GuildChannel] = list(kept_text_channels.values()) + list(kept_voice_channels.values())
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

    # Ensure team categories remain strictly above 'Night Spend'
    if night_spend_cat and night_spend_cat.position <= category.position:
        try:
            await night_spend_cat.edit(position=category.position + 1)
        except Exception:
            pass

    # Ensure 'Vaelkry logs' remains at the bottom
    if logs_cat:
        try:
            await logs_cat.edit(position=len(guild.categories) + 5)
        except Exception:
            pass

    return category, created_channels


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
