"""
Vaelkry Dev Labs - Multi-Agent Configuration Module
Loads and validates environment variables for both Developer and Moderator agents.
"""

import os
import sys
from dataclasses import dataclass, field
from typing import Dict, List
from dotenv import load_dotenv

# Ensure UTF-8 console output for Windows systems
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Load environment variables from .env file
load_dotenv()


@dataclass
class AgentConfig:
    key: str
    name: str
    role: str
    category: str  # "developer" or "moderator"
    team: str  # "team_vasan", "team_vijay", or "executives"
    env_token_key: str
    token: str = field(repr=False)
    next_tags: List[str] = field(default_factory=list)


@dataclass
class SystemConfig:
    gemini_api_key: str = field(repr=False)
    guild_id: int = 0
    project_channel_id: int = 0
    gemini_models: List[str] = field(
        default_factory=lambda: [
            "gemini-3.5-flash",
            "gemini-3.1-flash-lite",
            "gemini-3.8-flash",
            "gemini-flash-latest",
        ]
    )
    agents: Dict[str, AgentConfig] = field(default_factory=dict)

    @property
    def dev_agents(self) -> Dict[str, AgentConfig]:
        return {k: v for k, v in self.agents.items() if v.category == "developer"}

    @property
    def mod_agents(self) -> Dict[str, AgentConfig]:
        return {k: v for k, v in self.agents.items() if v.category == "moderator"}

    @property
    def team_vasan_agents(self) -> Dict[str, AgentConfig]:
        return {k: v for k, v in self.agents.items() if v.team == "team_vasan"}

    @property
    def team_vijay_agents(self) -> Dict[str, AgentConfig]:
        return {k: v for k, v in self.agents.items() if v.team == "team_vijay"}


def load_config() -> SystemConfig:
    """
    Validates and loads all configured bot credentials and server settings.
    Supports both Team Vasan, Team Vijay, and Executive Moderator agents.
    """
    missing_vars: List[str] = []

    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not gemini_key:
        missing_vars.append("GEMINI_API_KEY")

    guild_id_str = os.getenv("GUILD_ID", "").strip()
    if not guild_id_str:
        missing_vars.append("GUILD_ID")

    channel_id_str = os.getenv("PROJECT_CHANNEL_ID", "").strip()
    if not channel_id_str:
        missing_vars.append("PROJECT_CHANNEL_ID")

    # Team Vasan Developer Agents (5) - Core Required
    vasan_definitions = [
        ("ttf_vasan", "TTF Vasan", "Team Lead & Hype Commander", "developer", "team_vasan", "BOT_TOKEN_TTF_VASAN", ["pradeep"]),
        ("pradeep", "Pradeep Ranganathan", "Tech Lead & Solutions Architect", "developer", "team_vasan", "BOT_TOKEN_PRADEEP", ["mamitha", "kayadu"]),
        ("mamitha", "Mamitha", "UI/UX Designer", "developer", "team_vasan", "BOT_TOKEN_MAMITHA", ["kayadu", "muthazhagi"]),
        ("kayadu", "Kayadu", "Backend & DevOps Engineer", "developer", "team_vasan", "BOT_TOKEN_KAYADU", ["muthazhagi"]),
        ("muthazhagi", "Muthazhagi", "QA & Security Lead", "developer", "team_vasan", "BOT_TOKEN_MUTHAZHAGI", []),
    ]

    # Team Vijay Developer Agents (5)
    vijay_definitions = [
        ("vijay", "Vijay", "Team Lead (Team Vijay) & Thalapathy Swagger", "developer", "team_vijay", "BOT_TOKEN_VIJAY", []),
        ("sivakarthikeyan", "Sivakarthikeyan", "Timing Punch King & Chief Roaster", "developer", "team_vijay", "BOT_TOKEN_SIVA", []),
        ("anirudh", "Anirudh", "Rockstar Vibe & BGM Lead", "developer", "team_vijay", "BOT_TOKEN_ANIRUDH", []),
        ("trisha", "Trisha", "Cool Girl Sarcasm & Aesthetic Lead", "developer", "team_vijay", "BOT_TOKEN_TRISHA", []),
        ("lokesh", "Lokesh", "Action-First & Dark Humor Director", "developer", "team_vijay", "BOT_TOKEN_LOKESH", []),
    ]

    # Executive Moderator Agents (2) - Core Required
    mod_definitions = [
        ("sadie", "SadieSink", "Executive Moderator & Onboarding Lead", "moderator", "executives", "BOT_TOKEN_SADIE", []),
        ("millie", "MillieBobbyBrown", "Executive Moderator & Chief Audit Officer", "moderator", "executives", "BOT_TOKEN_MILLIE", []),
    ]

    agent_configs: Dict[str, AgentConfig] = {}

    # Check and load core required bots (Team Vasan & Executive Suite)
    for key, name, role, category, team, env_key, next_tags in vasan_definitions + mod_definitions:
        token = os.getenv(env_key, "").strip()
        if not token:
            missing_vars.append(env_key)
        else:
            agent_configs[key] = AgentConfig(
                key=key,
                name=name,
                role=role,
                category=category,
                team=team,
                env_token_key=env_key,
                token=token,
                next_tags=next_tags,
            )

    # Check and load Team Vijay bots (if tokens provided in .env, connect!)
    for key, name, role, category, team, env_key, next_tags in vijay_definitions:
        token = os.getenv(env_key, "").strip()
        if token:
            agent_configs[key] = AgentConfig(
                key=key,
                name=name,
                role=role,
                category=category,
                team=team,
                env_token_key=env_key,
                token=token,
                next_tags=next_tags,
            )
        else:
            import logging
            logging.getLogger("VaelkryDevLabs.Config").info(
                f"Team Vijay bot token '{env_key}' is not set in .env. Bot '{name}' will connect once token is added."
            )

    if missing_vars:
        raise ValueError(
            f"Missing required environment variables in .env:\n  - "
            + "\n  - ".join(missing_vars)
        )

    try:
        guild_id = int(guild_id_str)
    except ValueError:
        raise ValueError(f"GUILD_ID must be a valid integer, got: {guild_id_str}")

    try:
        project_channel_id = int(channel_id_str)
    except ValueError:
        raise ValueError(f"PROJECT_CHANNEL_ID must be a valid integer, got: {channel_id_str}")

    custom_model = os.getenv("GEMINI_MODEL", "").strip()
    models = ["gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-3.8-flash", "gemini-flash-latest"]
    if custom_model:
        models.insert(0, custom_model)

    return SystemConfig(
        gemini_api_key=gemini_key,
        guild_id=guild_id,
        project_channel_id=project_channel_id,
        gemini_models=models,
        agents=agent_configs,
    )
