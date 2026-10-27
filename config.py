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
            "gemini-flash-lite-latest",
            "gemini-3-flash-preview",
            "gemini-3.8-flash",
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


    @property
    def team_messi_agents(self) -> Dict[str, AgentConfig]:
        return {k: v for k, v in self.agents.items() if v.team == "team_messi"}

    @property
    def team_dhoni_agents(self) -> Dict[str, AgentConfig]:
        return {k: v for k, v in self.agents.items() if v.team == "team_dhoni"}

    @property
    def team_elon_agents(self) -> Dict[str, AgentConfig]:
        return {k: v for k, v in self.agents.items() if v.team == "team_elon"}

    @property
    def team_tony_agents(self) -> Dict[str, AgentConfig]:
        return {k: v for k, v in self.agents.items() if v.team in ("team_tony", "team_stark")}

    @property
    def team_stark_agents(self) -> Dict[str, AgentConfig]:
        return self.team_tony_agents


# Corporate Engineering Squads Catalog
SQUADS: Dict[str, dict] = {
    "team_vasan": {
        "name": "Team Vaasan",
        "lead": "ttf_vasan",
        "members": ["ttf_vasan", "pradeep", "mamitha", "kayadu", "muthazhagi"],
        "domain": "Full-Stack Web3 & Rapid Product Delivery",
    },
    "team_vijay": {
        "name": "Team Vijay",
        "lead": "vijay",
        "members": ["vijay", "sivakarthikeyan", "anirudh", "trisha", "lokesh"],
        "domain": "Cross-Platform Ecosystems, Cinematic Media & Performance",
    },
    "team_messi": {
        "name": "Team Messi",
        "lead": "messi",
        "members": ["messi", "ronaldo", "neymar", "haaland", "mbappe"],
        "domain": "High-Speed Systems, Micro-Optimizations & Algorithm Architecture",
    },
    "team_dhoni": {
        "name": "Team Dhoni",
        "lead": "dhoni",
        "members": ["dhoni", "virat", "rohit", "jadeja", "hardik"],
        "domain": "Clutch Incident Management, High-Pressure Production Fixes & Core Reliability",
    },
    "team_elon": {
        "name": "Team Elon",
        "lead": "elon",
        "members": ["elon", "mrbeast", "steve_jobs", "bill_gates", "kevin_mitnick"],
        "domain": "Tech Titans & Mavericks (Autonomous AI Systems, Viral Infrastructure & Cyber Engineering)",
    },
    "team_tony": {
        "name": "Team Tony",
        "lead": "tony",
        "members": ["tony", "tom_cruise", "brad_pitt", "johnny_depp", "walter_white"],
        "domain": "Hollywood & Cult Legends (Win32 Systems Internals, High-Stakes Operations & Heisenberg Architecture)",
    },
}
# Backward compatibility alias
SQUADS["team_stark"] = SQUADS["team_tony"]

# Bot Token Environment Variable Catalog
BOT_TOKENS: Dict[str, str] = {
    # Team Vaasan
    "ttf_vasan": os.getenv("BOT_TOKEN_TTF_VASAN", "").strip(),
    "pradeep": os.getenv("BOT_TOKEN_PRADEEP", "").strip(),
    "mamitha": os.getenv("BOT_TOKEN_MAMITHA", "").strip(),
    "kayadu": os.getenv("BOT_TOKEN_KAYADU", "").strip(),
    "muthazhagi": os.getenv("BOT_TOKEN_MUTHAZHAGI", "").strip(),
    # Team Vijay
    "vijay": os.getenv("BOT_TOKEN_VIJAY", "").strip(),
    "sivakarthikeyan": os.getenv("BOT_TOKEN_SIVA", "").strip(),
    "anirudh": os.getenv("BOT_TOKEN_ANIRUDH", "").strip(),
    "trisha": os.getenv("BOT_TOKEN_TRISHA", "").strip(),
    "lokesh": os.getenv("BOT_TOKEN_LOKESH", "").strip(),
    # Executive Suite
    "sadie": os.getenv("BOT_TOKEN_SADIE", "").strip(),
    "millie": os.getenv("BOT_TOKEN_MILLIE", "").strip(),
    # Team Messi
    "messi": os.getenv("BOT_TOKEN_MESSI", "").strip(),
    "ronaldo": os.getenv("BOT_TOKEN_RONALDO", "").strip(),
    "neymar": os.getenv("BOT_TOKEN_NEYMAR", "").strip(),
    "haaland": os.getenv("BOT_TOKEN_HAALAND", "").strip(),
    "mbappe": os.getenv("BOT_TOKEN_MBAPPE", "").strip(),
    # Team Dhoni
    "dhoni": os.getenv("BOT_TOKEN_DHONI", "").strip(),
    "virat": os.getenv("BOT_TOKEN_VIRAT", "").strip(),
    "rohit": os.getenv("BOT_TOKEN_ROHIT", "").strip(),
    "jadeja": os.getenv("BOT_TOKEN_JADEJA", "").strip(),
    "hardik": os.getenv("BOT_TOKEN_HARDIK", "").strip(),
    # Team Elon (Tech Titans & Mavericks)
    "elon": os.getenv("BOT_TOKEN_ELON", "").strip(),
    "mrbeast": os.getenv("BOT_TOKEN_MRBEAST", "").strip(),
    "steve_jobs": (os.getenv("BOT_TOKEN_STEVE_JOBS", "") or os.getenv("BOT_TOKEN_STEVEJOBS", "")).strip(),
    "bill_gates": (os.getenv("BOT_TOKEN_BILL_GATES", "") or os.getenv("BOT_TOKEN_BILLGATES", "")).strip(),
    "kevin_mitnick": (os.getenv("BOT_TOKEN_KEVIN_MITNICK", "") or os.getenv("BOT_TOKEN_KEVINMITNICK", "")).strip(),
    # Team Tony (Hollywood & Cult Legends, formerly Team Stark)
    "tony": (os.getenv("BOT_TOKEN_TONY", "") or os.getenv("BOT_TOKEN_STARK", "")).strip(),
    "tom_cruise": (os.getenv("BOT_TOKEN_TOM_CRUISE", "") or os.getenv("BOT_TOKEN_TOMCRUISE", "")).strip(),
    "brad_pitt": (os.getenv("BOT_TOKEN_BRAD_PITT", "") or os.getenv("BOT_TOKEN_BRADPITT", "")).strip(),
    "johnny_depp": (os.getenv("BOT_TOKEN_JOHNNY_DEPP", "") or os.getenv("BOT_TOKEN_JOHNNYDEPP", "")).strip(),
    "walter_white": (os.getenv("BOT_TOKEN_WALTER_WHITE", "") or os.getenv("BOT_TOKEN_WALTERWHITE", "")).strip(),
    "stark": (os.getenv("BOT_TOKEN_TONY", "") or os.getenv("BOT_TOKEN_STARK", "")).strip(),
}


def load_config() -> SystemConfig:
    """
    Validates and loads all configured bot credentials and server settings.
    Supports Team Vaasan, Team Vijay, Team Messi, Team Dhoni, Team Elon, Team Tony, and Executive Suite.
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

    # Team Messi Developer Agents (5) - High-Speed Systems & Algorithms
    messi_definitions = [
        ("messi", "Messi", "Team Lead & Algorithmic Maestro", "developer", "team_messi", "BOT_TOKEN_MESSI", []),
        ("ronaldo", "Ronaldo", "High-Performance Engineer & Deploy Striker", "developer", "team_messi", "BOT_TOKEN_RONALDO", []),
        ("neymar", "Neymar", "Motion Dynamics & Creative Frontend Specialist", "developer", "team_messi", "BOT_TOKEN_NEYMAR", []),
        ("haaland", "Haaland", "Big Data Cruncher & Latency Destroyer", "developer", "team_messi", "BOT_TOKEN_HAALAND", []),
        ("mbappe", "Mbappe", "Ultra-Fast Edge Routing & Microservices Lead", "developer", "team_messi", "BOT_TOKEN_MBAPPE", []),
    ]

    # Team Dhoni Developer Agents (5) - Clutch Incident Management & Reliability
    dhoni_definitions = [
        ("dhoni", "Dhoni", "Team Lead & Clutch Reliability Commander", "developer", "team_dhoni", "BOT_TOKEN_DHONI", []),
        ("virat", "Virat", "High-Intensity Code Reviewer & Core Performance Engineer", "developer", "team_dhoni", "BOT_TOKEN_VIRAT", []),
        ("rohit", "Rohit", "Chief Solutions Architect & Vadapav Chill Engineer", "developer", "team_dhoni", "BOT_TOKEN_ROHIT", []),
        ("jadeja", "Jadeja", "Sharp Defense, Security & Memory Leak Hunter", "developer", "team_dhoni", "BOT_TOKEN_JADEJA", []),
        ("hardik", "Hardik", "Swagger All-Rounder & Production Hotfix Specialist", "developer", "team_dhoni", "BOT_TOKEN_HARDIK", []),
    ]

    # Team Elon Developer Agents (5) - Tech Titans & Mavericks
    elon_definitions = [
        ("elon", "Elon Musk", "Team Lead & Techno-King (Multi-Agent Swarms & Autonomous AI)", "developer", "team_elon", "BOT_TOKEN_ELON", []),
        ("mrbeast", "MrBeast", "Viral Distribution & Mass Scale Maestro", "developer", "team_elon", "BOT_TOKEN_MRBEAST", []),
        ("steve_jobs", "Steve Jobs", "Chief Product Designer & Perfectionist Visionary", "developer", "team_elon", "BOT_TOKEN_STEVE_JOBS", []),
        ("bill_gates", "Bill Gates", "Global Systems Architect & Foundations Lead", "developer", "team_elon", "BOT_TOKEN_BILL_GATES", []),
        ("kevin_mitnick", "Kevin Mitnick", "Master Hacker & Cyber Penetration Specialist", "developer", "team_elon", "BOT_TOKEN_KEVIN_MITNICK", []),
    ]

    # Team Tony Developer Agents (5) - Hollywood & Cult Legends (formerly Team Stark)
    tony_definitions = [
        ("tony", "Tony Stark", "Team Lead & Systems Internals Master (Reverse Eng & Win32)", "developer", "team_tony", "BOT_TOKEN_TONY", []),
        ("tom_cruise", "Tom Cruise", "High-Risk Mission Specialist & Maverick Operations Lead", "developer", "team_tony", "BOT_TOKEN_TOM_CRUISE", []),
        ("brad_pitt", "Brad Pitt", "Chaos Engineering & Rogue Operations Lead", "developer", "team_tony", "BOT_TOKEN_BRAD_PITT", []),
        ("johnny_depp", "Johnny Depp", "Eccentric Creative & Outlaw Specialist", "developer", "team_tony", "BOT_TOKEN_JOHNNY_DEPP", []),
        ("walter_white", "Walter White", "Chemical Purity & Zero-Defect Code Architect", "developer", "team_tony", "BOT_TOKEN_WALTER_WHITE", []),
    ]
    stark_definitions = tony_definitions

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

    # Check and load optional squads (Team Vijay, Team Messi, Team Dhoni, Team Elon, Team Tony)
    optional_squads = [
        ("Team Vijay", vijay_definitions),
        ("Team Messi", messi_definitions),
        ("Team Dhoni", dhoni_definitions),
        ("Team Elon", elon_definitions),
        ("Team Tony", tony_definitions),
    ]

    import logging
    cfg_logger = logging.getLogger("VaelkryDevLabs.Config")

    for squad_name, definitions in optional_squads:
        for key, name, role, category, team, env_key, next_tags in definitions:
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
                cfg_logger.debug(
                    f"{squad_name} bot token '{env_key}' is not set in .env. Bot '{name}' will connect once token is added."
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
