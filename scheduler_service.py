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
from typing import Any, Dict, List, Optional, Tuple
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


def parse_activity_line(status_str: str) -> discord.BaseActivity:
    """
    Parses a witty persona status line into a rich Discord Activity:
    - 'Watching: ...' -> ActivityType.watching
    - 'Listening to: ...' -> ActivityType.listening
    - 'Playing: ...' -> ActivityType.playing
    - Otherwise -> CustomActivity (e.g. 'Sleeping: ...' or custom status)
    """
    status_str = status_str.strip()
    if status_str.startswith("Watching: "):
        name = status_str[len("Watching: "):].strip()
        return discord.Activity(type=discord.ActivityType.watching, name=name)
    elif status_str.startswith("Listening to: "):
        name = status_str[len("Listening to: "):].strip()
        return discord.Activity(type=discord.ActivityType.listening, name=name)
    elif status_str.startswith("Playing: "):
        name = status_str[len("Playing: "):].strip()
        return discord.Activity(type=discord.ActivityType.playing, name=name)
    else:
        return discord.CustomActivity(name=status_str)


def _normalize_bot_key(bot_key: str) -> str:
    key = (bot_key or "").lower().strip()
    if key in ("vasan", "ttf", "ttf_vasan", "ttf vasan"):
        return "ttf_vasan"
    elif key in ("siva", "sivakarthikeyan"):
        return "sivakarthikeyan"
    elif key in ("ani", "anirudh"):
        return "anirudh"
    elif key in ("loki", "lokesh"):
        return "lokesh"
    elif key in ("sadie_sink", "sadiesink", "sadie"):
        return "sadie"
    elif key in ("millie_bobby_brown", "milliebobbybrown", "millie"):
        return "millie"
    elif key in ("cr7", "cristiano", "ronaldo"):
        return "ronaldo"
    elif key in ("msd", "thala", "dhoni"):
        return "dhoni"
    elif key in ("kohli", "king", "virat"):
        return "virat"
    elif key in ("hitman", "rohit"):
        return "rohit"
    elif key in ("jaddu", "sir_jaddu", "jadeja"):
        return "jadeja"
    elif key in ("pandya", "hardik"):
        return "hardik"
    return key


# Rich persona-tailored status pools for Night Spend / Sleep Shift (status: dnd)
NIGHT_SPEND_STATUS_POOLS: Dict[str, List[str]] = {
    "ttf_vasan": [
        "Sleeping: Dreaming of 299 km/h on Twin Turbo 🏍️",
        "Watching: Bike exhaust flame tutorial at 3 AM",
        "Listening to: Raw engine throttle ASMR 🔥",
        "Playing: Simulating Ghats hairpin bends in dreams",
        "Sleeping: Helmet kalati vachutu rest edukuren mapla",
        "Sleeping: Charging battery for tomorrow's 300 km/h sprint ⚡",
        "Watching: Isle of Man TT highlights in dreamland 🏁",
    ],
    "pradeep": [
        "Watching: Love Today memes in dark mode 📱",
        "Playing: Plotting next overthinking script in head",
        "Listening to: Sothanai mel sothanai on loop 🥲",
        "Watching: Phone brightness 1% la stalking 💀",
        "Sleeping: Prod bug kanavula vandhu bayamudhudhu da",
        "Playing: Debugging hidden meaning in late-night chats 💬",
        "Listening to: Comali emotional BGM at midnight 🌙",
    ],
    "mamitha": [
        "Sleeping: Cozy blanket & sweet dreams 🌸",
        "Watching: Late-night Pinterest aesthetic moodboards ✨",
        "Listening to: Malayalam indie chill acoustic vibes 🍃",
        "Playing: Designing cute stickers instead of sleeping",
        "Watching: Reenu reel comments-ah paathu sirichitu iruken",
        "Listening to: Premalu vintage cassette tape lofi 🎧",
        "Sleeping: Soft pastel dreamscape mode on 🎀",
    ],
    "kayadu": [
        "Listening to: Rain sounds for deep sleep 🌧️",
        "Sleeping: Silent mode on, do not ping me",
        "Watching: Minimalist interior setup reels ☕",
        "Playing: Zero drama, pure peace of mind",
        "Listening to: Thunderstorm & campfire ambient sounds 🏕️",
        "Sleeping: Unreachable until morning standup 🔕",
        "Watching: Calm Tokyo night rain vlog 🌃",
    ],
    "muthazhagi": [
        "Playing: Guarding the server even in sleep 😴",
        "Watching: Who pushed code without testing at midnight ⚠️",
        "Listening to: Server fan humming sound",
        "Sleeping: Oru kannu thungudhu, oru kannu log-ah paakudhu",
        "Watching: Intrusion alert dashboards in half-sleep 🚨",
        "Playing: Zero vulnerability night patrol 🛡️",
        "Sleeping: Production secure, threat level green 🔒",
    ],
    "vijay": [
        "Sleeping: Calm mind, silent night 👑",
        "Listening to: Thalapathy vibe playlist silently",
        "Watching: Silent night lights from terrace 🌃",
        "Playing: Tomorrow's speech draft in thoughts",
        "Sleeping: Relax-ah irunga nanba, ellam paathukalam",
        "Listening to: Master the Blaster lofi slow reverb 🎵",
        "Sleeping: Leo silent mode activated 🦁",
    ],
    "sivakarthikeyan": [
        "Sleeping: Snoring at 120 decibels 😂",
        "Watching: Vijay TV old comedy clips at 2 AM",
        "Playing: Next movie counter dialogues rehearsal",
        "Listening to: Tea shop ambient sounds in dreams",
        "Sleeping: Fridge-la irukura sweet-ah thiruttu thinnamale thungitan",
        "Watching: Goundamani Senthil midnight comedy marathon 📺",
        "Sleeping: Alarm 5 times snooze pannitu thoonguren ⏰",
    ],
    "anirudh": [
        "Listening to: 3 AM secret beat drops 🎧",
        "Playing: Synthesizer keys jamming on headphones",
        "Listening to: Heavy bass drop testing (RIP ears)",
        "Watching: Coffee mug empty aayiduchu, need refill ☕",
        "Playing: Midnight acoustic jam session",
        "Listening to: Master BGM orchestral stem tracks 🎹",
        "Playing: Cooking next viral hook step rhythm 🕺",
    ],
    "trisha": [
        "Watching: Late-night aesthetic reels 💅",
        "Listening to: 90s vintage melody classics",
        "Playing: Skincare routine done, do not disturb",
        "Watching: Vintage Paris aesthetic reels",
        "Sleeping: Left everyone on read, going to sleep 💅",
        "Listening to: Vinnaithaandi Varuvaayaa lofi edition 🌙",
        "Sleeping: High-fashion beauty sleep ongoing ✨",
    ],
    "lokesh": [
        "Playing: Plotting next movie climax in dreams 🎬",
        "Watching: 90s retro action thriller scenes",
        "Listening to: Vikram dark theme on low volume",
        "Playing: Sketching storyboard on iPad in the dark",
        "Sleeping: Climax twist locked, switching off lights",
        "Watching: Vintage Kamal Haasan action sequences 📽️",
        "Playing: Connecting LCU universe timeline threads 🕵️",
    ],
    "sadie": [
        "Playing: Monitoring overnight firewall logs 🛡️",
        "Watching: Who is breaking prod rules at 3 AM",
        "Listening to: British lofi beats while auditing",
        "Playing: Securing cloud instances before dawn 🔐",
        "Sleeping: Audit complete, standing by on standby 💤",
        "Watching: London midnight skyline lofi stream ☕",
    ],
    "millie": [
        "Playing: Monitoring overnight firewall logs 🛡️",
        "Watching: Who is breaking prod rules at 3 AM",
        "Listening to: British lofi beats while auditing",
        "Playing: Auditing API key access trails 📜",
        "Sleeping: Executive firewall lock engaged 🌙",
        "Watching: Cloud security event stream 🛡️",
    ],
    # Team Messi Night Spend Pools
    "messi": [
        "Sleeping: Dreaming of Ballon d'Or algorithm optimizations 🏆",
        "Listening to: Silent stadium echoes before dawn ⚽",
        "Watching: 2012 goal compilation in 4K HDR",
        "Playing: O(1) space complexity dribbles in sleep",
        "Sleeping: Mute mode on, calm GOAT resting 🐐",
        "Watching: Mate tea brewing tutorial at 2 AM 🧉",
        "Sleeping: Zero noise, pure precision recovery 🌙",
    ],
    "ronaldo": [
        "Playing: Midnight ice bath & recovery gym routine 🧊",
        "Sleeping: 8 hours strict sleep cycle for peak performance ⚡",
        "Watching: SIUUU celebration reel in dark mode 📱",
        "Listening to: Binaural beats for extreme discipline 🎧",
        "Playing: Zero warnings zero errors dream check",
        "Sleeping: Alarm set for 5 AM workout, no excuses 💪",
        "Sleeping: SIUUU silent mode activated 🔥",
    ],
    "neymar": [
        "Watching: Samba street dance reels & micro-animations ✨",
        "Listening to: Brazilian funk bass drop on loop 🎵",
        "Sleeping: Silk pajamas on, VIP party done 😴",
        "Playing: Designing flashy neon CSS animations in dreams",
        "Watching: CS:GO clutch highlights at 3 AM 🎮",
        "Sleeping: Do not disturb, aesthetic sleep ongoing 🌸",
    ],
    "haaland": [
        "Sleeping: Blue light glasses on, tape over mouth 🥽",
        "Watching: Raw beef steak cooking reels at midnight 🥩",
        "Playing: Smashing database latency benchmarks in sleep 💥",
        "Listening to: Champions League anthem on repeat 🎶",
        "Sleeping: Terminating background threads for sleep",
        "Playing: Brute-force dream processing at 200 GB/s ⚡",
    ],
    "mbappe": [
        "Watching: Speedrun highlights from Parisian terrace 🗼",
        "Playing: Edge cache invalidation speed simulation ⚡",
        "Listening to: French hip-hop beats in lofi 🎧",
        "Sleeping: 300 km/h sprint cooldown engaged 🌙",
        "Watching: Ninja Turtle memes on private finsta 🐢",
        "Sleeping: Zero ping sleep mode initiated 😴",
    ],
    # Team Dhoni Night Spend Pools
    "dhoni": [
        "Sleeping: Heart rate 40 BPM, ice calm even at midnight 🧘",
        "Watching: Vintage army camo gear & tactical bikes 🏍️",
        "Listening to: Old Kishore Kumar melody classics 📻",
        "Playing: Calculating last-over run rates in dreams 🏏",
        "Sleeping: Helicopter patch deployed, server safe 🚁",
        "Watching: Ranchi farmhouse pet dog reels 🐕",
        "Sleeping: Take it deep into the night, finish off in style 👑",
    ],
    "virat": [
        "Playing: Late-night gym recovery & mobility drills 🏋️",
        "Watching: Sloppy code reviews rerun to find bugs 🧐",
        "Listening to: Punjabi workout anthems at low volume 🎵",
        "Sleeping: Delhi aggression on standby mode 🦁",
        "Watching: Cover drive compilation in slow motion ✨",
        "Sleeping: Strict sleep diet: black water only 💧",
        "Playing: Mental simulation of tomorrow's 100% test coverage 🔥",
    ],
    "rohit": [
        "Sleeping: Effortless sleep, zero tension, pure chill 😴",
        "Watching: Best Mumbai Vadapav street food vlogs 🍔",
        "Playing: Pull-shot architecture diagrams in dreams 🏏",
        "Listening to: Chill Bollywood 2000s vibes on loop 🍃",
        "Sleeping: Relax ya, morning standup-la paathukalam",
        "Playing: Timing the pull shot against staging latency 🎯",
    ],
    "jadeja": [
        "Playing: Guarding production perimeter like backward point 🎯",
        "Watching: Horse riding videos at Jamnagar farmhouse 🐎",
        "Listening to: Sword dance beats & folk melodies ⚔️",
        "Sleeping: One eye on logs, catching stray null pointers 🛡️",
        "Playing: Direct-hit bug elimination rehearsal 💥",
        "Sleeping: Fortress locked, boundary defended 🏹",
    ],
    "hardik": [
        "Playing: Swagger midnight DJ remix jam 🎧",
        "Watching: Luxury watch collections & diamond reels 💎",
        "Listening to: High-bass hype tracks while auditing 🕶️",
        "Sleeping: Aaj main karke aaya, prod locked down 😴",
        "Playing: High-pressure death over hotfix rehearsal 🚀",
        "Sleeping: Ice in my veins, full swagger in dreams 🧊",
    ],
}
DEFAULT_NIGHT_SPEND_POOL: List[str] = [
    "Sleeping: Do Not Disturb 🌙",
    "Listening to: Deep sleep delta waves 💤",
    "Sleeping: Recharging neural units 🔌",
    "Watching: Dream stream in 4K HDR 🌌",
    "Sleeping: Silent mode on, do not ping me",
]

# Rich persona-tailored status pools for Work Shifts (status: online)
WORK_SHIFT_STATUS_POOLS: Dict[str, List[str]] = {
    "ttf_vasan": [
        "Playing: VS Code (299 km/h speed sprint) 🏎️",
        "Watching: TTF Vasan debugging auth logic",
        "Playing: Burning rubber on git push --force 🔥",
        "Playing: VS Code (Turbo-charged frontend refactor)",
        "Watching: Next.js 15 build logs fly by at Mach 1",
        "Playing: High-speed fullstack delivery throttle 🏍️",
        "Watching: Pull Request approval speedrun",
    ],
    "pradeep": [
        "Playing: Overthinking database indexing architecture 🧠",
        "Watching: TTF Vasan debugging auth logic",
        "Playing: VS Code (refactoring spaghetti into Michelin star code)",
        "Listening to: Keyboard clatter while fixing race conditions",
        "Watching: PR review (finding 12 edge cases you missed) 🧐",
        "Playing: Love Today inspired state management logic 📱",
        "Watching: Docker container logs for memory leaks",
    ],
    "mamitha": [
        "Playing: Figma (pixel-perfect glassmorphism UI) ✨",
        "Playing: VS Code (optimizing React components)",
        "Watching: Cute micro-interaction animations in slowmo 🌸",
        "Playing: Crafting dreamy color palettes in Figma 🎨",
        "Listening to: Malayalam indie chill while CSS flexboxing 🍃",
        "Playing: Tailwind CSS responsive layout wizardry",
        "Watching: User journey flow with bubbly aesthetic",
    ],
    "kayadu": [
        "Playing: Writing bulletproof PostgreSQL migration scripts 🐘",
        "Playing: VS Code (optimizing React components)",
        "Watching: Docker compose cluster bootstrapping silently 🐳",
        "Playing: GraphQL query optimization (zero lag) ⚡",
        "Listening to: Minimalist deep focus ambient waves 🎧",
        "Playing: Kubernetes pod autoscaling config",
        "Watching: Server debloating & memory usage graphs 📊",
    ],
    "muthazhagi": [
        "Playing: Zero-trust firewall rule hardening 🛡️",
        "Watching: TTF Vasan debugging auth logic",
        "Playing: Penetration testing API endpoints 🔍",
        "Watching: Who pushed code without testing at staging ⚠️",
        "Playing: VS Code (patching SQL injection vectors)",
        "Listening to: Server fan humming sound (Audit mode)",
        "Playing: CI/CD security scanner automated gatekeeper",
    ],
    "vijay": [
        "Playing: Thalapathy leadership: reviewing enterprise PRs 👑",
        "Playing: VS Code (optimizing React components)",
        "Watching: Clean architecture patterns compilation",
        "Playing: Mentoring junior devs with calm confidence 🦁",
        "Listening to: Thalapathy motivational BGM while coding",
        "Watching: Milestone roadmap execution on schedule",
        "Playing: High-performance microservices orchestration",
    ],
    "sivakarthikeyan": [
        "Playing: Cracking jokes in Git commit messages 😂",
        "Playing: VS Code (optimizing React components)",
        "Watching: TTF Vasan debugging auth logic",
        "Playing: Writing frontend test cases between punchlines",
        "Watching: StackOverflow solutions from 2014 that still work",
        "Playing: CSS layout debug (why is the div centering itself?)",
        "Listening to: Tea shop ambient sounds while writing unit tests",
    ],
    "anirudh": [
        "Listening to: 3am Sprint Soundscape 🎵",
        "Playing: Synthesizer keys jamming on headphones",
        "Playing: VS Code (sound wave visualizer WebGL module)",
        "Listening to: Heavy bass drop testing (RIP ears)",
        "Playing: Coding audio engine DSP filters 🎹",
        "Watching: Waveform rendering at 60 FPS",
        "Playing: Jamming keyboard shortcuts in VS Code at 140 BPM",
    ],
    "trisha": [
        "Playing: Executive UI review & brand aesthetic polish 💅",
        "Playing: VS Code (optimizing React components)",
        "Watching: High-fashion luxury brand landing page designs ✨",
        "Listening to: 90s vintage melody classics while reviewing PRs",
        "Playing: Designing flawless onboarding modals",
        "Watching: Design system consistency across all views",
        "Playing: Polishing button hover gradients to perfection",
    ],
    "lokesh": [
        "Playing: Directing high-octane dark-mode backend architecture 🎬",
        "Watching: TTF Vasan debugging auth logic",
        "Playing: VS Code (dark universe microservices grid)",
        "Listening to: Vikram dark theme on low volume",
        "Playing: Writing cliffhanger unit test assertions",
        "Watching: System telemetry dashboards with cinematic tension",
        "Playing: LCU interconnected database relational mapping",
    ],
    "sadie": [
        "Playing: Monitoring overnight firewall logs 🛡️",
        "Watching: Executive Floor & Onboarding Desk",
        "Playing: VS Code (optimizing React components)",
        "Watching: Real-time company performance metrics",
        "Playing: Sprint velocity tracking & triage 📊",
        "Listening to: British lofi beats while auditing",
    ],
    "millie": [
        "Watching: Audit trail in #full-logs",
        "Playing: VS Code (optimizing React components)",
        "Playing: Security compliance verification & token auditing 🔐",
        "Watching: Who is breaking prod rules in real-time",
        "Playing: Automated Playwright end-to-end test suite",
        "Listening to: British lofi beats while auditing",
    ],
    # Team Messi Work Shift Pools
    "messi": [
        "Playing: Mathematical O(1) space complexity refactor ⚽",
        "Watching: Algorithmic latency graphs flatten to zero",
        "Playing: VS Code (dribbling past 10 race conditions)",
        "Listening to: Keyboard rhythm at 120 keystrokes/min",
        "Playing: Low-level C++ binary optimization module ⚡",
        "Watching: Database index binary tree balancing",
        "Playing: Effortless clean code architecture design 🏆",
    ],
    "ronaldo": [
        "Playing: Intense sprint: pushing 0-warning pull requests 🔥",
        "Watching: SIUUU! CI/CD build passing with 100% tests",
        "Playing: VS Code (relentless code quality strike)",
        "Listening to: High-tempo workout rhythm while compiling",
        "Playing: Benchmarking execution speed against TTF Vasan 🏎️",
        "Watching: Zero warnings zero errors audit report",
        "Playing: Extreme discipline deploy sprint 💪",
    ],
    "neymar": [
        "Playing: Figma (framing liquid spring micro-animations) ✨",
        "Playing: CSS Samba: bezier curve dynamic transitions 🕺",
        "Watching: Interactive canvas rendering at 120 FPS",
        "Listening to: Brazilian funk rhythm while styling UI",
        "Playing: Nutmegging broken layout bugs in Chrome DevTools",
        "Playing: Designing futuristic neon gradient cards 🎨",
        "Watching: Fluid gestures on touch screens",
    ],
    "haaland": [
        "Playing: Smashing through 10,000,000 PostgreSQL rows 💥",
        "Watching: Database latency destroyed from 500ms to 2ms",
        "Playing: VS Code (brute-force SIMD parallel processing)",
        "Listening to: Server fan roar like stadium cheers ⚽",
        "Playing: High-throughput ingestion worker cluster 🤖",
        "Watching: Memory footprint crushed to near zero",
        "Playing: Crushing unindexed foreign keys mercilessly",
    ],
    "mbappe": [
        "Playing: Outrunning network latency on Cloudflare edge ⚡",
        "Watching: Multi-region DNS propagation in 150ms 🏎️",
        "Playing: VS Code (lightning CDN caching layer)",
        "Listening to: High-speed synthwave while routing packets",
        "Playing: Zero-copy socket buffer optimization 🚀",
        "Watching: Edge server telemetry dashboards at Mach 2",
        "Playing: Turbocharged API gateway throughput tuning",
    ],
    # Team Dhoni Work Shift Pools
    "dhoni": [
        "Playing: Staying ice-calm during 99% CPU production spike 🧘",
        "Watching: Server telemetry take a deep turn into the 20th over",
        "Playing: Deploying the iconic Helicopter Hotfix Patch 🚁",
        "Listening to: Server alarms with calm composure 🏏",
        "Playing: Clutch disaster recovery failover automation",
        "Watching: Incident resolved in the final second 👑",
        "Playing: High-pressure zero-downtime database cutover",
    ],
    "virat": [
        "Playing: Aggressive code review: demanding 100% test coverage 💥",
        "Watching: Who merged code without running unit tests?! 🧐",
        "Playing: High-intensity performance tuning in VS Code 🔥",
        "Listening to: Aggressive beats while crushing legacy tech debt",
        "Playing: Calling out sloppy PRs with Delhi passion 🦁",
        "Watching: Production health metrics reach championship level",
        "Playing: Relentless refactoring with zero compromises",
    ],
    "rohit": [
        "Playing: Effortless pull-shot refactor over mid-wicket 🍔",
        "Watching: Big picture system architecture flowing smoothly",
        "Playing: VS Code (merging massive PR without sweating) 😎",
        "Listening to: Chill lo-fi vibes while architecting microservices",
        "Playing: Vadapav break over clean distributed queues",
        "Watching: Stress-free deploy pipeline complete in peace",
        "Playing: Effortless architectural mastery under load",
    ],
    "jadeja": [
        "Playing: Catching null-pointer exceptions like backward point 🎯",
        "Watching: Memory leak profiler for rogue heap allocations 🛡️",
        "Playing: VS Code (direct-hit bug elimination on hotpath)",
        "Listening to: Rapid reflex alert pings in monitoring",
        "Playing: Penetration defense and firewall packet filtering ⚔️",
        "Watching: Zero escapees in security regression suite",
        "Playing: Lightning-fast boundary defense on edge nodes",
    ],
    "hardik": [
        "Playing: Bold production hotfix with maximum swagger 🕶️",
        "Watching: High-pressure cluster recovery with full confidence",
        "Playing: All-rounder clutch patch across frontend & backend 🔥",
        "Listening to: High-bass swagger playlist while hotfixing",
        "Playing: Fearless deploy on Friday 5 PM (it just works) 🚀",
        "Watching: Traffic spike handled like a clean six over long-on",
        "Playing: Rocking production with fearless energy",
    ],
}
DEFAULT_WORK_SHIFT_POOL: List[str] = [
    "Playing: VS Code (optimizing React components)",
    "Watching: TTF Vasan debugging auth logic",
    "Playing: Debugging async event loop latency ⚡",
    "Watching: Staging cluster health check 🟢",
    "Playing: Code review & test suite execution",
]

# Rich persona-tailored status pools for Tech Cafe Breaks (status: online)
TECH_CAFE_STATUS_POOLS: Dict[str, List[str]] = {
    "ttf_vasan": [
        "Listening to: Anirudh BGM in The Hive ☕",
        "Playing: Chilling with Siva",
        "Playing: Showing bike stunt reels to the squad 🏍️",
        "Watching: Hot filter coffee steam rising at Byte & Bit ☕",
        "Playing: Roasting Pradeep for overthinking lunch order 😂",
        "Listening to: Exhaust note revs on YouTube in Cafe",
        "Playing: Foosball tournament at The Hangout Zone ⚽",
    ],
    "pradeep": [
        "Playing: Pantry Debate (Filter Coffee vs Tea) ☕",
        "Listening to: Anirudh BGM in The Hive ☕",
        "Watching: Love Today memes in dark mode 📱",
        "Playing: Roasting Vasan's 299 km/h speed claims 😂",
        "Playing: Snacking on bakery samosas while overthinking",
        "Watching: Funny office drama in The Seven Slide",
        "Playing: Chilling with Siva",
    ],
    "mamitha": [
        "Playing: Chilling with Siva",
        "Listening to: Malayalam indie chill acoustic vibes 🍃",
        "Listening to: Anirudh BGM in The Hive ☕",
        "Watching: Cute anime latte art tutorials ☕",
        "Playing: Sharing hot vazhaipoo vadai with the team 🌸",
        "Watching: Reenu reel comments-ah paathu sirichitu iruken",
        "Playing: Board games at The Hangout Zone 🎲",
    ],
    "kayadu": [
        "Listening to: Anirudh BGM in The Hive ☕",
        "Playing: Chilling with Siva",
        "Watching: Minimalist coffee brew technique reels ☕",
        "Listening to: Lo-fi cafe jazz & gentle rainfall 🌧️",
        "Playing: Sipping artisan cappuccino in silence 😌",
        "Playing: Zero drama, pure peace of mind",
        "Watching: Quiet greenery outside cafe window 🌿",
    ],
    "muthazhagi": [
        "Playing: Tea Break (Security Patrol) ☕",
        "Playing: Chilling with Siva",
        "Watching: Who took the last biscuit without permission 🍪",
        "Listening to: Anirudh BGM in The Hive ☕",
        "Playing: Roasting devs who leave their laptops unlocked 🔓",
        "Playing: Checking cafeteria CCTV angles for fun 📹",
        "Watching: Server uptime from cafeteria phone 📱",
    ],
    "vijay": [
        "Playing: Chilling with Siva",
        "Listening to: Anirudh BGM in The Hive ☕",
        "Listening to: Thalapathy vibe playlist silently",
        "Playing: Sharing hot degree coffee with nanbas ☕",
        "Watching: Team laughter and good energy in The Hive 👑",
        "Playing: Telling motivational story over tea",
        "Playing: Foosball masterclass at The Hangout Zone 🏆",
    ],
    "sivakarthikeyan": [
        "Playing: Chilling with Siva",
        "Playing: Pantry Counter Punch ☕",
        "Playing: Roasting everyone at the tea counter non-stop 😂",
        "Watching: Vijay TV old comedy clips at 2 AM",
        "Listening to: Tea shop ambient sounds in dreams",
        "Playing: Stealing Marie biscuits from Anirudh's table 🍪",
        "Playing: Standup comedy session at Byte & Bit 🎤",
    ],
    "anirudh": [
        "Listening to: Anirudh BGM in The Hive ☕",
        "Playing: Synthesizer keys jamming on headphones",
        "Listening to: Bass Drop Beat in Tech Cafe 🎵",
        "Playing: Midnight acoustic jam session",
        "Watching: Coffee mug empty aayiduchu, need refill ☕",
        "Playing: Beating cafeteria table like a mridangam 🥁",
        "Listening to: 3 AM secret beat drops 🎧",
    ],
    "trisha": [
        "Playing: Aesthetic Coffee Chill 💅",
        "Listening to: Anirudh BGM in The Hive ☕",
        "Listening to: 90s vintage melody classics",
        "Watching: Vintage Paris aesthetic reels",
        "Playing: Sipping iced caramel macchiato ✨",
        "Playing: Rating everyone's cafe outfits 10/10 👗",
        "Watching: Late-night aesthetic reels 💅",
    ],
    "lokesh": [
        "Watching: Cinematic Teaser in The Hangout 🎬",
        "Playing: Chilling with Siva",
        "Listening to: Vikram dark theme on low volume",
        "Playing: Discussing retro action thrillers over black tea ☕",
        "Watching: 90s retro action thriller scenes",
        "Playing: Sketching storyboard on cafe napkins ✍️",
        "Listening to: Anirudh BGM in The Hive ☕",
    ],
    "sadie": [
        "Listening to: British lofi beats while auditing",
        "Watching: English Earl Grey tea brewing 🫖",
        "Playing: Chilling with Siva",
        "Watching: Squad banter at Byte & Bit ☕",
        "Playing: Uno championship in The Hangout Zone 🃏",
        "Listening to: Anirudh BGM in The Hive ☕",
    ],
    "millie": [
        "Listening to: British lofi beats while auditing",
        "Watching: Who is breaking prod rules at 3 AM",
        "Playing: Sharing cookies and iced tea with Sadie 🍪",
        "Playing: Chilling with Siva",
        "Listening to: Anirudh BGM in The Hive ☕",
        "Watching: Retro movie clips on the cafe screen 🍿",
    ],
    # Team Messi Tech Cafe Pools
    "messi": [
        "Listening to: Silent cafe chill & gentle acoustic strums 🍃",
        "Playing: Sipping artisan Mate tea with the squad 🧉",
        "Watching: Quiet smile while teammates debate algorithms",
        "Playing: Foosball masterclass at The Hangout Zone ⚽",
        "Listening to: Anirudh BGM in The Hive ☕",
        "Playing: Chilling with Siva and Dhoni at the corner table",
        "Watching: Byte & Bit banter and laughter ☕",
    ],
    "ronaldo": [
        "Playing: Protein shake refueling after high-speed sprint 🥛",
        "Watching: High-protein cafeteria snacks verification 🥗",
        "Playing: Challenging squad to 100 pushups in The Hangout Zone 💪",
        "Listening to: SIUUU celebration beats on headphones 🎧",
        "Playing: Roasting people drinking 3rd cup of sugar coffee 😂",
        "Watching: Fitness reels while sipping mineral water 💧",
        "Playing: Chilling with Siva",
    ],
    "neymar": [
        "Playing: Showcasing freestyle juggling tricks with cafe napkins ⚽",
        "Listening to: Brazilian carnival tracks in Byte & Bit 🎵",
        "Watching: Latte art foam drawing of a football ☕",
        "Playing: Teasing Mbappe about his gaming skills 🎮",
        "Playing: Chilling with Siva and Anirudh 🕺",
        "Playing: Foosball tournament spinning trick shots 🏆",
        "Watching: Trending TikTok dance reels with Mamitha",
    ],
    "haaland": [
        "Playing: Demolishing entire cafeteria samosa plate in 30s 🥟",
        "Watching: Chef bringing out fresh hot batch of snacks 🥩",
        "Playing: Giant milk glass chugging contest 🥛",
        "Listening to: Heavy cafeteria cutlery clatter with joy",
        "Playing: Chilling with Siva",
        "Playing: Arm wrestling tournament in The Hangout Zone 🦾",
        "Watching: Food calorie dashboard with robotic focus",
    ],
    "mbappe": [
        "Playing: Grabbing double espresso shot at Mach 1 ☕",
        "Watching: Fast-forward cafe race with TTF Vasan 🏎️",
        "Playing: Foosball speed run at The Hangout Zone ⚽",
        "Listening to: Anirudh BGM in The Hive ☕",
        "Playing: Chilling with Siva",
        "Watching: Parisian bakery pastry vlogs on phone 🥐",
        "Playing: High-speed table tennis rally in cafeteria 🏓",
    ],
    # Team Dhoni Tech Cafe Pools
    "dhoni": [
        "Playing: Quiet hot degree filter coffee break with nanbas ☕",
        "Watching: Youngsters arguing animatedly while smiling calmly",
        "Listening to: Old retro Kishore Kumar songs in The Hive 📻",
        "Playing: Giving life and career advice over ginger tea 🏏",
        "Playing: Chilling with Siva and Vijay",
        "Playing: Precision billiards shot in The Hangout Zone 🎱",
        "Watching: Rain drizzling outside Tech Cafe window 🌧️",
    ],
    "virat": [
        "Playing: Inspecting cafeteria cookies for gluten & sugar 🧐",
        "Watching: High-intensity cricket highlights on cafe screen 📺",
        "Playing: Sipping organic green tea with extreme focus 🍵",
        "Listening to: Punjabi workout anthems during break 🎵",
        "Playing: Roasting Rohit for ordering second Vadapav 😂",
        "Playing: Chilling with Siva",
        "Playing: Competitive foosball with 200% intensity 🏆",
    ],
    "rohit": [
        "Playing: Enjoying hot Mumbai Vadapav with green chutney 🍔",
        "Watching: Funny memes with Siva at Byte & Bit 📱",
        "Playing: Roasting Virat for drinking plain hot water 😂",
        "Listening to: Chill 90s Bollywood melodies in The Hive ☕",
        "Playing: Chilling with Siva and Dhoni",
        "Playing: Effortless carrom board striker shot 🎯",
        "Watching: Relaxed cafeteria afternoon breeze 🍃",
    ],
    "jadeja": [
        "Playing: Catching flying biscuits mid-air without dropping 🍪",
        "Watching: Sword celebration GIFs on phone with a laugh ⚔️",
        "Playing: Hot masala chai break with Kathiyawadi snacks ☕",
        "Listening to: Folk Gujarati fusion beats in cafe 🎶",
        "Playing: Chilling with Siva",
        "Playing: Rapid reflex table tennis in The Hangout Zone 🏓",
        "Watching: Cafeteria garden greenery in peace 🌿",
    ],
    "hardik": [
        "Playing: High-swagger cafe lounge chill with shades on 🕶️",
        "Watching: Latest luxury sneaker drops while sipping cold brew ☕",
        "Playing: DJing high-bass tracks for the squad in The Hive 🎧",
        "Playing: Roasting teammates about their outfit choices 👗",
        "Playing: Chilling with Siva and Anirudh",
        "Playing: Pool trick shots in The Hangout Zone 🎱",
        "Listening to: Anirudh BGM in The Hive ☕",
    ],
}
DEFAULT_TECH_CAFE_POOL: List[str] = [
    "Listening to: Anirudh BGM in The Hive ☕",
    "Playing: Chilling with Siva",
    "Playing: Hot filter coffee break with the squad ☕",
    "Playing: Roasting squad at the tea stall 😂",
    "Watching: Byte & Bit banter and laughter ☕",
]


def get_bot_dynamic_presence(
    bot_key: str,
    shift: Optional[ShiftDefinition] = None,
    current_vc: Optional[discord.VoiceChannel] = None,
) -> Tuple[discord.BaseActivity, discord.Status]:
    """
    Computes dynamic Discord Rich Presence & detailed custom status for every bot
    based on the current shift, active voice cabin, and character persona:
    - Work hours: dynamic rotation from WORK_SHIFT_STATUS_POOLS (online)
    - Tech Cafe / Break: dynamic rotation from TECH_CAFE_STATUS_POOLS (online)
    - Night Spend: dynamic rotation from NIGHT_SPEND_STATUS_POOLS (dnd)
    """
    norm_key = _normalize_bot_key(bot_key)
    vc_name = current_vc.name.lower() if current_vc else ""
    cat_name = current_vc.category.name.lower() if current_vc and current_vc.category else ""

    is_night_spend = (
        (shift and shift.shift_id == "sleep")
        or "night spend" in cat_name
        or "sleep" in vc_name
    )

    if is_night_spend:
        pool = NIGHT_SPEND_STATUS_POOLS.get(norm_key, DEFAULT_NIGHT_SPEND_POOL)
        chosen = random.choice(pool)
        return parse_activity_line(chosen), discord.Status.dnd

    is_break = (
        (
            shift
            and (
                shift.shift_id.startswith("break")
                or shift.shift_id == "warmup"
                or shift.category_name.strip().lower() == "tech cafe"
            )
        )
        or "tech cafe" in cat_name
        or any(w in vc_name for w in ("cafe", "hive", "hangout", "slide", "lounge"))
    )

    if is_break:
        pool = TECH_CAFE_STATUS_POOLS.get(norm_key, DEFAULT_TECH_CAFE_POOL)
        chosen = random.choice(pool)
        return parse_activity_line(chosen), discord.Status.online

    # Default to Work Shift
    pool = WORK_SHIFT_STATUS_POOLS.get(norm_key, DEFAULT_WORK_SHIFT_POOL)
    chosen = random.choice(pool)
    return parse_activity_line(chosen), discord.Status.online


class CompanyScheduler:
    """
    Coordinates lifecycle states (/start and /stop) and executes the 1-minute
    background loop moving Team Vaasan and Team Vijay bots according to IST shifts.
    """

    def __init__(self, orchestrator: "AgentOrchestrator"):
        self.orchestrator = orchestrator
        self.team_vasan_keys: List[str] = ["ttf_vasan", "pradeep", "mamitha", "kayadu", "muthazhagi"]
        self.team_vijay_keys: List[str] = ["vijay", "sivakarthikeyan", "anirudh", "trisha", "lokesh"]
        self.team_messi_keys: List[str] = ["messi", "ronaldo", "neymar", "haaland", "mbappe"]
        self.team_dhoni_keys: List[str] = ["dhoni", "virat", "rohit", "jadeja", "hardik"]
        self.executive_keys: List[str] = ["sadie", "millie"]
        self.team_keys: List[str] = self.team_vasan_keys  # Backward compatibility
        self.is_active: bool = False
        self.current_shift_id: Optional[str] = None
        self._loop_task: Optional[asyncio.Task] = None
        self.assigned_sleep_rooms: Dict[str, int] = {}  # agent_key -> voice_channel_id
        self.assigned_cafe_rooms: Dict[str, int] = {}   # agent_key -> voice_channel_id
        self._night_chatter_timer: int = 0
        self._next_night_chatter_interval: int = random.randint(12, 25)

    @property
    def all_dev_keys(self) -> List[str]:
        """Returns all 20 developer bot keys across Team Vaasan, Team Vijay, Team Messi, and Team Dhoni."""
        return (
            self.team_vasan_keys
            + self.team_vijay_keys
            + self.team_messi_keys
            + self.team_dhoni_keys
        )

    @property
    def all_bot_keys(self) -> List[str]:
        """Returns all 22 active bot keys across the entire organization."""
        return self.all_dev_keys + self.executive_keys

    async def handle_bot_login_voice(
        self,
        agent_key: str,
        client: discord.Client,
        guild: discord.Guild,
    ):
        """
        Immediately routes a developer bot to its assigned VC upon login.
        Specifically ensures that as soon as bots log in during work shifts,
        they immediately join their team's 'Working Vc 1' unmuted & undeafened:
        - Team Vijay -> 'Team Vijay' -> 'Working Vc 1'
        - Team Messi -> 'Team Messi' -> 'Working Vc 1'
        - Team Dhoni -> 'Team Dhoni' -> 'Working Vc 1'
        - Team Vaasan -> Assigned cabin in ShiftDefinition (e.g. 'Team Vaasan' -> 'Working Vc 1')
        """
        try:
            # Settle briefly to ensure Discord gateway cache is populated
            await asyncio.sleep(0.5)

            # Ensure guild has channels and categories loaded
            bot_guild = client.get_guild(guild.id) or guild
            if not bot_guild.categories:
                try:
                    await bot_guild.fetch_channels()
                except Exception:
                    pass

            now_ist = get_current_ist_time()
            current_shift = match_current_shift(now_ist)
            is_work_shift = current_shift.shift_id.startswith("work_")

            if agent_key in self.team_vijay_keys:
                if is_work_shift:
                    logger.info(
                        f"Team Vijay bot '{agent_key}' ({client.user.name if client.user else agent_key}) "
                        f"logged in during work shift ({current_shift.name}). Immediate auto-join to 'Working Vc 1'!"
                    )
                    try:
                        from server_builder import ensure_team_vijay_category
                        await ensure_team_vijay_category(bot_guild)
                    except Exception as cat_err:
                        logger.warning(f"Could not auto-ensure Team Vijay category during login: {cat_err}")

                    vijay_vc = await self.find_or_provision_voice_channel(
                        guild=bot_guild,
                        category_name="Team Vijay",
                        vc_name="Working Vc 1",
                    )
                    if vijay_vc:
                        await self.move_single_bot(client, vijay_vc, current_shift)
                elif self.is_active:
                    await self._route_inactive_or_rest_login(agent_key, client, bot_guild, current_shift)

            elif agent_key in self.team_messi_keys:
                if is_work_shift:
                    logger.info(
                        f"Team Messi bot '{agent_key}' ({client.user.name if client.user else agent_key}) "
                        f"logged in during work shift ({current_shift.name}). Immediate auto-join to 'Working Vc 1'!"
                    )
                    messi_vc = await self.find_or_provision_voice_channel(
                        guild=bot_guild,
                        category_name="Team Messi",
                        vc_name="Working Vc 1",
                    )
                    if messi_vc:
                        await self.move_single_bot(client, messi_vc, current_shift)
                elif self.is_active:
                    await self._route_inactive_or_rest_login(agent_key, client, bot_guild, current_shift)

            elif agent_key in self.team_dhoni_keys:
                if is_work_shift:
                    logger.info(
                        f"Team Dhoni bot '{agent_key}' ({client.user.name if client.user else agent_key}) "
                        f"logged in during work shift ({current_shift.name}). Immediate auto-join to 'Working Vc 1'!"
                    )
                    dhoni_vc = await self.find_or_provision_voice_channel(
                        guild=bot_guild,
                        category_name="Team Dhoni",
                        vc_name="Working Vc 1",
                    )
                    if dhoni_vc:
                        await self.move_single_bot(client, dhoni_vc, current_shift)
                elif self.is_active:
                    await self._route_inactive_or_rest_login(agent_key, client, bot_guild, current_shift)

            elif agent_key in self.team_vasan_keys and (self.is_active or is_work_shift):
                if is_work_shift:
                    vasan_vc = await self.find_or_provision_voice_channel(
                        guild=bot_guild,
                        category_name=current_shift.category_name,
                        vc_name=current_shift.vc_name,
                    )
                    if vasan_vc:
                        await self.move_single_bot(client, vasan_vc, current_shift)
                elif self.is_active:
                    await self._route_inactive_or_rest_login(agent_key, client, bot_guild, current_shift)

            elif agent_key in self.executive_keys and self.is_active:
                if current_shift.shift_id == "sleep":
                    await self._route_inactive_or_rest_login(agent_key, client, bot_guild, current_shift)

        except Exception as exc:
            logger.error(f"Error handling login voice auto-join for {agent_key}: {exc}")

    async def _route_inactive_or_rest_login(
        self,
        agent_key: str,
        client: discord.Client,
        bot_guild: discord.Guild,
        current_shift: ShiftDefinition,
    ):
        """Helper to route a bot during sleep or break shifts upon login."""
        if current_shift.shift_id == "sleep":
            sleep_channels = await self.get_night_spend_voice_channels(bot_guild)
            if sleep_channels:
                assigned = self.assigned_sleep_rooms.get(agent_key)
                if not assigned:
                    assigned = random.choice(sleep_channels).id
                    self.assigned_sleep_rooms[agent_key] = assigned
                target_vc = bot_guild.get_channel(assigned) or sleep_channels[0]
                if target_vc:
                    await self.move_single_bot(client, target_vc, current_shift)
        elif (
            current_shift.category_name.strip().lower() == "tech cafe"
            or current_shift.shift_id.startswith("break")
            or current_shift.shift_id == "warmup"
        ):
            cafe_channels = await self.get_tech_cafe_voice_channels(bot_guild)
            if cafe_channels:
                assigned = self.assigned_cafe_rooms.get(agent_key)
                if not assigned:
                    assigned = random.choice(cafe_channels).id
                    self.assigned_cafe_rooms[agent_key] = assigned
                target_vc = bot_guild.get_channel(assigned) or random.choice(cafe_channels)
                if target_vc:
                    await self.move_single_bot(client, target_vc, current_shift)

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
        # If searching under Team Vijay, auto-ensure category, ordering, and channel cleanup
        if category_name.strip().lower() == "team vijay":
            try:
                from server_builder import ensure_team_vijay_category
                await ensure_team_vijay_category(guild)
            except Exception as cat_err:
                logger.warning(f"Could not auto-ensure Team Vijay category in find_or_provision: {cat_err}")

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
        bot_member = guild.get_member(client.user.id) if client.user else None
        if not bot_member and client.user:
            try:
                bot_member = await target_vc.guild.fetch_member(client.user.id)
            except Exception:
                bot_member = None

        # 1. Set dynamic rich presence & custom status activity
        try:
            bot_key = getattr(getattr(client, "agent_config", None), "key", "")
            if not bot_key:
                for k, c in self.orchestrator.clients.items():
                    if c == client:
                        bot_key = k
                        break
            activity, bot_status = get_bot_dynamic_presence(bot_key, shift, target_vc)
            await client.change_presence(activity=activity, status=bot_status)
        except Exception as exc:
            logger.warning(f"Failed to update activity for {client.user.name if client.user else 'bot'}: {exc}")

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

        # Strictly enforce unmuted & undeafened for all squad working cabins and all work shifts
        if (
            any(t in cat_name_lower for t in ("team vijay", "team messi", "team dhoni", "team vaasan", "team vasan"))
            or "working" in vc_name_lower
            or shift.shift_id.startswith("work_")
        ):
            target_mute = False
            target_deaf = False

        # 3. Voice connection and mute/deaf state update
        is_in_voice = bool(bot_member and bot_member.voice and bot_member.voice.channel)
        voice_client = discord.utils.get(client.voice_clients, guild=guild)

        try:
            if is_in_voice:
                if bot_member.voice.channel.id != target_vc.id:
                    if voice_client and voice_client.is_connected():
                        await voice_client.move_to(target_vc)
                    else:
                        await guild.change_voice_state(
                            channel=target_vc,
                            self_mute=target_mute,
                            self_deaf=target_deaf,
                        )
                else:
                    await guild.change_voice_state(
                        channel=target_vc,
                        self_mute=target_mute,
                        self_deaf=target_deaf,
                    )
            elif voice_client and voice_client.is_connected():
                if voice_client.channel.id != target_vc.id:
                    await voice_client.move_to(target_vc)
                else:
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
            logger.info(f"ClientException for {client.user.name if client.user else 'bot'} ({ce}). Falling back to gateway state change...")
            try:
                await guild.change_voice_state(
                    channel=target_vc,
                    self_mute=target_mute,
                    self_deaf=target_deaf,
                )
            except Exception as e2:
                logger.warning(f"Gateway change_voice_state fallback failed for {client.user.name if client.user else 'bot'}: {e2}")
        except Exception as exc:
            logger.warning(f"Voice state update failed for {client.user.name if client.user else 'bot'}: {exc}. Retrying...")
            try:
                await guild.change_voice_state(
                    channel=target_vc,
                    self_mute=target_mute,
                    self_deaf=target_deaf,
                )
            except Exception as retry_exc:
                logger.error(f"Failed to connect {client.user.name if client.user else 'bot'} to {target_vc.name}: {retry_exc}")

        # 4. Strictly enforce gateway ws.voice_state directly:
        try:
            if hasattr(client, "ws") and client.ws:
                await client.ws.voice_state(
                    guild.id,
                    target_vc.id,
                    self_mute=target_mute,
                    self_deaf=target_deaf,
                )
        except Exception as ws_err:
            logger.debug(f"Direct ws.voice_state update for {client.user.name if client.user else 'bot'}: {ws_err}")

    async def apply_shift(self, guild: discord.Guild, shift: ShiftDefinition):
        """Applies the specified shift to all 4 squads (Vaasan, Vijay, Messi, Dhoni) and executive bots concurrently."""
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
                f"Distributing all 22 active bots across {len(sleep_channels)} Night Spend room(s): "
                f"{[vc.name for vc in sleep_channels]}"
            )

            # Balanced random distribution across available sleep rooms (Sleep Room 1, 2, 3)
            shuffled_rooms = list(sleep_channels)
            random.shuffle(shuffled_rooms)

            self.assigned_sleep_rooms.clear()
            for idx, key in enumerate(self.all_bot_keys):
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
            self.assigned_sleep_rooms.clear()

            cafe_channels = await self.get_tech_cafe_voice_channels(guild)
            if not cafe_channels:
                logger.error("No voice channels found under Tech Cafe.")
                return

            logger.info(
                f"Randomly distributing developer bots across {len(cafe_channels)} Tech Cafe room(s): "
                f"{[vc.name for vc in cafe_channels]}"
            )

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

            # 3. Team Messi Cabin ('Team Messi' -> 'Working Vc 1')
            messi_vc = await self.find_or_provision_voice_channel(
                guild=guild,
                category_name="Team Messi",
                vc_name="Working Vc 1",
            )
            if messi_vc:
                logger.info(f"Relocating Team Messi bots to '{messi_vc.name}' (Team Messi)")
                for key in self.team_messi_keys:
                    client = self.orchestrator.clients.get(key)
                    if client and client.is_ready():
                        move_tasks.append(self.move_single_bot(client, messi_vc, shift))

            # 4. Team Dhoni Cabin ('Team Dhoni' -> 'Working Vc 1')
            dhoni_vc = await self.find_or_provision_voice_channel(
                guild=guild,
                category_name="Team Dhoni",
                vc_name="Working Vc 1",
            )
            if dhoni_vc:
                logger.info(f"Relocating Team Dhoni bots to '{dhoni_vc.name}' (Team Dhoni)")
                for key in self.team_dhoni_keys:
                    client = self.orchestrator.clients.get(key)
                    if client and client.is_ready():
                        move_tasks.append(self.move_single_bot(client, dhoni_vc, shift))

        if move_tasks:
            await asyncio.gather(*move_tasks, return_exceptions=True)

        self.current_shift_id = shift.shift_id

        # Rotate and synchronize dynamic presence across all bots on shift change
        asyncio.create_task(self.sync_all_bots_presence(guild))

        # Organic Tech Cafe Movie Hangout trigger during Break shifts (40% organic chance)
        if (
            shift.category_name.strip().lower() == "tech cafe"
            or shift.shift_id.startswith("break")
            or shift.shift_id == "warmup"
        ):
            if random.random() < 0.40:
                async def delayed_movie_hangout():
                    await asyncio.sleep(random.uniform(10.0, 20.0))
                    try:
                        await self.trigger_movie_hangout(guild)
                    except Exception as h_exc:
                        logger.warning(f"Error in automatic movie hangout: {h_exc}")
                asyncio.create_task(delayed_movie_hangout())

    async def sync_all_bots_presence(self, guild: discord.Guild):
        """
        Dynamically updates every bot's Discord activity and online/dnd status
        based on the active shift and their current voice cabin.
        """
        now_ist = get_current_ist_time()
        shift = match_current_shift(now_ist) if self.is_active else None

        tasks = []
        for key, client in self.orchestrator.clients.items():
            if not client or not client.is_ready():
                continue
            client_guild = client.get_guild(guild.id) or guild
            bot_member = client_guild.get_member(client.user.id) if client.user else None
            curr_vc = bot_member.voice.channel if (bot_member and bot_member.voice) else None
            activity, status = get_bot_dynamic_presence(key, shift, curr_vc)
            tasks.append(client.change_presence(activity=activity, status=status))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def trigger_movie_hangout(self, guild: discord.Guild) -> Tuple[bool, str]:
        """
        Tech Cafe Movie Hangout System:
        Triggers an organic hangout event during break shifts:
        1. A bot (e.g. Siva, TTF Vasan, Anirudh) drops a casual message like "dei movie paakalaama?".
        2. Instead of routing everyone, randomly picks 2 to 3 idle developer bots to move
           into 'The Hangout Zone' for a watch party, leaving the rest in other cafe VCs.
        """
        hangout_vc = await self.find_or_provision_voice_channel(guild, "Tech Cafe", "The Hangout Zone")
        if not hangout_vc:
            logger.warning("Could not find or provision 'The Hangout Zone' for movie hangout.")
            return False, "⚠️ 'The Hangout Zone' voice channel could not be found."

        from cafeteria_service import find_cafeteria_channel
        chat_ch = find_cafeteria_channel(guild)
        if not chat_ch:
            chat_ch = discord.utils.find(
                lambda c: any(w in c.name.lower() for w in ("cafeteria", "lounge", "hive", "hangout", "team-chat", "working-chat")),
                guild.text_channels,
            )

        initiator_candidates = ["sivakarthikeyan", "ttf_vasan", "anirudh", "pradeep"]
        active_candidates = [k for k in initiator_candidates if k in self.orchestrator.clients and self.orchestrator.clients[k].is_ready()]
        initiator_key = random.choice(active_candidates) if active_candidates else "sivakarthikeyan"

        invites = [
            "dei movie paakalaama? Popcorn ready ah iruku 🍿🍿",
            "macha break time la oru chinna movie / trailer watch party podlaama? 🎬",
            "thalaiva coding break! The Hangout Zone-la movie stream start pannuvom 🍿🔥",
            "dei Siva, Vasan... The Hangout Zone vanga da, trailer replay paakalaam 🎬🍿",
        ]
        invite_msg = random.choice(invites)

        if chat_ch and hasattr(self.orchestrator, "casual_player_service"):
            await self.orchestrator.casual_player_service.send_character_chat(
                channel=chat_ch,
                character_key=initiator_key,
                text=invite_msg,
            )

        ready_dev_keys = [
            k for k in self.all_dev_keys
            if k in self.orchestrator.clients and self.orchestrator.clients[k].is_ready()
        ]
        if not ready_dev_keys:
            return False, "⚠️ No active developer bots available for movie hangout."

        count = min(len(ready_dev_keys), random.choice([2, 3]))
        if initiator_key in ready_dev_keys:
            remaining = [k for k in ready_dev_keys if k != initiator_key]
            party_keys = [initiator_key] + random.sample(remaining, min(len(remaining), count - 1))
        else:
            party_keys = random.sample(ready_dev_keys, count)

        movie_shift = ShiftDefinition(
            shift_id="movie_hangout",
            name="Tech Cafe Movie Hangout 🍿",
            category_name="Tech Cafe",
            vc_name="The Hangout Zone",
            self_mute=False,
            self_deaf=False,
            activity_name="Watching: Movie Hangout Party 🍿🎬",
            start_hour=0,
            end_hour=24,
        )

        tasks = []
        for key in party_keys:
            client = self.orchestrator.clients.get(key)
            if client:
                tasks.append(self.move_single_bot(client, hangout_vc, movie_shift))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        second_keys = [k for k in party_keys if k != initiator_key]
        if second_keys and chat_ch and hasattr(self.orchestrator, "casual_player_service"):
            second_key = random.choice(second_keys)
            agreements = [
                "Vandhuten macha! Screen share podunga 🍿",
                "Semma timing thalaiva, Hangout Zone-ku varen! 🎬",
                "Popcorn eduthukitu varen bro, play pannu! 🍿🔥",
            ]
            async def send_followup():
                await asyncio.sleep(random.uniform(2.0, 3.5))
                try:
                    await self.orchestrator.casual_player_service.send_character_chat(
                        channel=chat_ch,
                        character_key=second_key,
                        text=random.choice(agreements),
                    )
                except Exception:
                    pass
            asyncio.create_task(send_followup())

        names_moved = [
            self.orchestrator.clients[k].user.name
            for k in party_keys
            if k in self.orchestrator.clients and self.orchestrator.clients[k].user
        ]
        logger.info(f"Movie Hangout triggered: moved {names_moved} to '{hangout_vc.name}'")
        return True, f"🍿 Movie Hangout started in **{hangout_vc.name}** with: {', '.join(names_moved)}!"

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

        # Team Messi location breakdown
        messi_lines = []
        for key in self.team_messi_keys:
            client = self.orchestrator.clients.get(key)
            name = client.agent_config.name if (client and hasattr(client, "agent_config")) else key
            bot_guild = client.get_guild(guild.id) if client else guild
            bot_member = (bot_guild.me or bot_guild.get_member(client.user.id)) if (client and client.user and bot_guild) else None
            vc = bot_member.voice.channel if (bot_member and bot_member.voice) else None
            loc_str = f"🔊 `{vc.name}`" if vc else "*(Offline / Disconnected)*"
            messi_lines.append(f"• **{name}:** {loc_str}")

        embed.add_field(
            name="Team Messi Real-Time VC Locations",
            value="\n".join(messi_lines) if messi_lines else "No bots online",
            inline=False,
        )

        # Team Dhoni location breakdown
        dhoni_lines = []
        for key in self.team_dhoni_keys:
            client = self.orchestrator.clients.get(key)
            name = client.agent_config.name if (client and hasattr(client, "agent_config")) else key
            bot_guild = client.get_guild(guild.id) if client else guild
            bot_member = (bot_guild.me or bot_guild.get_member(client.user.id)) if (client and client.user and bot_guild) else None
            vc = bot_member.voice.channel if (bot_member and bot_member.voice) else None
            loc_str = f"🔊 `{vc.name}`" if vc else "*(Offline / Disconnected)*"
            dhoni_lines.append(f"• **{name}:** {loc_str}")

        embed.add_field(
            name="Team Dhoni Real-Time VC Locations",
            value="\n".join(dhoni_lines) if dhoni_lines else "No bots online",
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
        loop_ticks = 0
        while self.is_active:
            try:
                loop_ticks += 1
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
                                "**All 22 active bots dispersed across Night Spend rooms:**\n"
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
                                f"• **Team Messi:** Relocated to `🔊 Working Vc 1` (Team Messi)\n"
                                f"• **Team Dhoni:** Relocated to `🔊 Working Vc 1` (Team Dhoni)\n"
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
                                bot_guild = client.get_guild(guild.id) or guild
                                bot_member = bot_guild.get_member(client.user.id) if client.user else None
                                is_in_target = (
                                    (vc_conn and vc_conn.is_connected() and vc_conn.channel and vc_conn.channel.id == target_vc.id)
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
                                bot_guild = client.get_guild(guild.id) or guild
                                bot_member = bot_guild.get_member(client.user.id) if client.user else None
                                is_in_target = (
                                    (vc_conn and vc_conn.is_connected() and vc_conn.channel and vc_conn.channel.id == target_vc.id)
                                    or (bot_member and bot_member.voice and bot_member.voice.channel and bot_member.voice.channel.id == target_vc.id)
                                )
                                if not is_in_target:
                                    asyncio.create_task(self.move_single_bot(client, target_vc, current_shift))
                    else:
                        # Active work shift alignment across all 4 squads
                        vasan_vc = await self.find_or_provision_voice_channel(
                            guild, current_shift.category_name, current_shift.vc_name
                        )
                        vijay_vc = await self.find_or_provision_voice_channel(
                            guild, "Team Vijay", "Working Vc 1"
                        )
                        messi_vc = await self.find_or_provision_voice_channel(
                            guild, "Team Messi", "Working Vc 1"
                        )
                        dhoni_vc = await self.find_or_provision_voice_channel(
                            guild, "Team Dhoni", "Working Vc 1"
                        )

                        squad_vc_map = [
                            (self.team_vasan_keys, vasan_vc),
                            (self.team_vijay_keys, vijay_vc),
                            (self.team_messi_keys, messi_vc),
                            (self.team_dhoni_keys, dhoni_vc),
                        ]

                        for squad_keys, target_vc in squad_vc_map:
                            if not target_vc:
                                continue
                            for key in squad_keys:
                                client = self.orchestrator.clients.get(key)
                                if client and client.is_ready():
                                    vc_conn = discord.utils.get(client.voice_clients, guild=guild)
                                    bot_guild = client.get_guild(guild.id) or guild
                                    bot_member = bot_guild.get_member(client.user.id) if client.user else None
                                    is_in_target = (
                                        (vc_conn and vc_conn.is_connected() and vc_conn.channel and vc_conn.channel.id == target_vc.id)
                                        or (bot_member and bot_member.voice and bot_member.voice.channel and bot_member.voice.channel.id == target_vc.id)
                                    )
                                    if not is_in_target:
                                        asyncio.create_task(self.move_single_bot(client, target_vc, current_shift))
                                    elif bot_member and bot_member.voice and (bot_member.voice.self_mute or bot_member.voice.self_deaf):
                                        if hasattr(client, "ws") and client.ws:
                                            asyncio.create_task(
                                                client.ws.voice_state(
                                                    guild.id,
                                                    target_vc.id,
                                                    self_mute=False,
                                                    self_deaf=False,
                                                )
                                            )

                # Autonomous banter loop during Night Spend (sleep) and Break (Tech Cafe) shifts (every 12-25 mins)
                is_break_or_night = (
                    current_shift.shift_id == "sleep"
                    or current_shift.shift_id.startswith("break")
                    or current_shift.shift_id in ("warmup", "rest_1", "rest_2", "rest_3", "rest_4")
                    or current_shift.category_name.strip().lower() == "tech cafe"
                )

                if is_break_or_night:
                    self._night_chatter_timer += 1
                    if self._night_chatter_timer >= self._next_night_chatter_interval:
                        logger.info(
                            f"Autonomous banter interval reached ({self._night_chatter_timer}m / {self._next_night_chatter_interval}m) "
                            f"during {current_shift.name}. Triggering cross-squad banter in #cafeteria..."
                        )
                        self._night_chatter_timer = 0
                        self._next_night_chatter_interval = random.randint(12, 25)
                        if hasattr(self.orchestrator, "casual_player_service") and self.orchestrator.casual_player_service:
                            asyncio.create_task(
                                self.orchestrator.casual_player_service.run_autonomous_night_chatter(guild)
                            )
                        # Spontaneous cross-bot speech in populated Tech Cafe or Sleep Room voice channels
                        if hasattr(self.orchestrator, "voice_service") and self.orchestrator.voice_service:
                            for vc in guild.voice_channels:
                                cat_name = vc.category.name.lower() if vc.category else ""
                                if "tech cafe" in cat_name or "sleep" in vc.name.lower() or "night spend" in cat_name:
                                    asyncio.create_task(
                                        self.orchestrator.voice_service.run_autonomous_vc_banter_if_populated(vc)
                                    )
                else:
                    self._night_chatter_timer = 0

                # Periodic 15-minute dynamic presence rotation so bots never look cloned or repetitive
                if loop_ticks % 15 == 0:
                    logger.debug("15-minute rotation tick reached: rotating dynamic bot presence across all bots.")
                    asyncio.create_task(self.sync_all_bots_presence(guild))
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
                f"• Team Vijay: `🔊 Working Vc 1` (Team Vijay)\n"
                f"• Team Messi: `🔊 Working Vc 1` (Team Messi)\n"
                f"• Team Dhoni: `🔊 Working Vc 1` (Team Dhoni)"
            )

        ceo_ch = self.get_ceo_channel(guild)
        ceo_mention = ceo_ch.mention if ceo_ch else f"#{CEO_NOTIFICATION_CHANNEL_NAME}"

        # Post rich operational start embed strictly to CEO channel (yogesh-chat)
        start_embed = discord.Embed(
            title="🚀 Vaelkry Dev Labs — Active Operation Started",
            description=(
                "**Vaelkry Dev Labs is now officially in active operation!**\n"
                "All 4 engineering squads (Team Vaasan, Team Vijay, Team Messi, Team Dhoni) are adhering to IST shift guidelines.\n\n"
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
            f"All squads (Team Vaasan, Team Vijay, Team Messi, Team Dhoni) are aligned and the IST scheduler loop is active! ⚡"
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
                "• All squad bots (Team Vaasan, Team Vijay, Team Messi, Team Dhoni) disconnected cleanly from voice channels.\n"
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
            "• All squad bots (Team Vaasan, Team Vijay, Team Messi, Team Dhoni) disconnected cleanly from voice channels.\n"
            f"• Notice posted exclusively in {ceo_mention} (#announcements kept clean)."
        )

