# ⚡ Vaelkry Dev Labs — Multi-Agent Enterprise Discord System

An autonomous multi-agent engineering and executive operations system built with **discord.py** and **Google GenAI** (Gemini). The system concurrently runs **7 Discord bot clients**:
- **5 Developer Agents** who hold structured engineering sprints in authentic **Tanglish** (Tamil-English blend) and adhere to a 24-hour corporate routine.
- **2 Executive Moderator Agents** providing real-time audit logging, automated onboarding, and dynamic CEO voice escort.

---

## 👥 The 7-Agent Squad

### 🛠️ Developer Squad (Team Vaasan)
| Agent | Role | Persona & Style | Key Responsibilities |
|---|---|---|---|
| **🏍️ TTF Vasan** | Team Lead & Hype Commander | High-speed bike throttle energy (299 km/h), massive hype, street-smart leader | Inspires team, sets aggressive goals, picks stack, hosts slash commands, tags Pradeep |
| **🧠 Pradeep Ranganathan** | Tech Lead & Solutions Architect | Quirky, sarcastic, practical tech genius (*Love Today / Comali / Dragon* vibe) | Architecture breakdown (Frontend, Backend, Auth, Microservices), hands off to Mamitha & Kayadu |
| **🎨 Mamitha** | UI/UX Designer | Cheerful, aesthetic perfectionist (*Premalu* Reenu energy), loves glassmorphism & clean UI | User flow, screen hierarchy, design system, color palette, micro-interactions, tags Kayadu |
| **⚙️ Kayadu** | DevOps & Backend Lead | Calm, poised, grounded, authoritative systems engineer ("No tension, cool-ah handle pannuvom") | Database schema (PostgreSQL), REST/GraphQL APIs, Docker setup, Redis caching, CI/CD, tags Muthazhagi |
| **🛡️ Muthazhagi** | QA & Security Auditor | Strict, razor-sharp, zero bug tolerance (*Paruthiveeran* fierce gatekeeper) | Edge case checklist, security audit (JWT, SQL injection, CORS, rate limiting), **Official Green Signal** |

### 👔 Executive Moderator Squad
| Agent | Role | Style | Key Responsibilities |
|---|---|---|---|
| **🌟 SadieSink** | Executive Moderator & Onboarding Lead | Elegant, professional, corporate hospitality | Welcomes new members in `#greeting` with an enterprise onboarding card, voice escort |
| **📋 MillieBobbyBrown** | Chief Audit Officer & Log Custodian | Vigilant, meticulous, real-time security auditor | Formats and logs all member joins/leaves, role changes, channel modifications, and voice updates to `#full-logs` |

---

## ⏰ Indian Standard Time (IST) 24-Hour Shift Routine

When company operations are activated via `/start`, an automated background worker checks the time every minute and moves all 5 Team Vaasan bots to their scheduled voice cabin, applies mute/deaf permissions, and sets their Discord custom activity status:

| Time Slot (IST) | Shift Name | Location (Category ➔ Voice Channel) | Flags | Custom Activity Status |
|---|---|---|---|---|
| **17:00 – 02:00** | Sleep | `Night Spend` ➔ `Sleep Room 1` | `self_mute=True`, `self_deaf=True` | `Sleeping in Night Spend 💤` |
| **02:00 – 03:00** | Warmup | `Tech Cafe` ➔ `The Hangout Zone` | Unmute, Undeafen | `Chai & Coffee ☕` |
| **03:00 – 05:00** | Work Shift 1 | `Team Vaasan` ➔ `Working Vc 1` | Normal | `Sprint 1 - System Dev 💻` |
| **05:00 – 06:00** | Rest Break 1 | `Tech Cafe` ➔ `The Seven Slide` | Normal | `Break - Gaming 🎮` |
| **06:00 – 08:00** | Work Shift 2 | `Team Vaasan` ➔ `Working Vc 2` | Normal | `Sprint 2 - Code & Logic ⚙️` |
| **08:00 – 09:00** | Rest Break 2 | `Tech Cafe` ➔ `Byte & Bit` | Normal | `Breakfast & Refreshment 🥪` |
| **09:00 – 11:00** | Work Shift 3 | `Team Vaasan` ➔ `Working Vc 1` | Normal | `Sprint 3 - UI Components 🎨` |
| **11:00 – 12:00** | Rest Break 3 | `Tech Cafe` ➔ `The Hive` | `self_deaf=True` | `Power Nap ⚡` |
| **12:00 – 14:00** | Work Shift 4 | `Team Vaasan` ➔ `Working Vc 2` | Undeafen | `Sprint 4 - APIs & Infra 🚢` |
| **14:00 – 15:00** | Rest Break 4 | `Tech Cafe` ➔ `The Hangout Zone` | Normal | `Lunch & Arcade Break 🍛` |
| **15:00 – 17:00** | Work Shift 5 | `Team Vaasan` ➔ `Working Vc 1` | Normal | `Sprint 5 - QA & Wrap 🛡️` |

---

## 🏢 CEO Handwritten Blueprint (`/reset_and_build_server`)

Executable by the Server Owner or Admin:
- Purges all old channels and categories.
- Strictly builds the blueprint structure:

```
📂 Yogesh Space
  • #yogesh-chat
  • 🔊 CEO vc

📂 Circular
  • #announcements
  • #greeting  (Onboarding Desk - SadieSink)

📂 Common Pantry
  • #cafeteria
  • #the-launchpad  (Official Project Launchpad)
  • #control-room
  • #managers-space

📂 Tech Cafe
  • 🔊 The Seven Slide
  • 🔊 Byte & Bit
  • 🔊 The Hive
  • 🔊 The Hangout Zone

📂 Team Vaasan
  • #working-chat
  • #team-chat
  • 🔊 Working Vc 1
  • 🔊 Working Vc 2

📂 Night Spend
  • 🔊 Sleep Room 1
  • 🔊 Sleep Room 2
  • 🔊 Sleep Room 3

📂 Vaelkry logs
  • #full-logs  (Audit & Security Logs - MillieBobbyBrown)
```

---

## 📈 Dynamic Team Scaling (`/teamcategory <team_name>`)

Allows admins to dynamically provision an isolated engineering workspace for any new team:
- Duplicates the template of `Team Vaasan`:
  * Category: `Team {team_name}`
  * Text: `#working-chat`, `#team-chat`
  * Voice: `Working Vc 1`, `Working Vc 2`
- **Strict Positioning**: Positioned right below `Team Vaasan` (and existing teams) and before `Vaelkry logs`.

---

## 🎙️ Executive Follower Mode & 24/7 Autonomous Floor Manager

SadieSink & MillieBobbyBrown operate as 24/7 fully autonomous floor managers:
- **`/follow`**:
  * SadieSink and MillieBobbyBrown join the Voice Channel where the CEO is currently present.
  * Whenever the CEO moves to another VC, both bots dynamically track and relocate into that VC instantly.
- **`/unfollow`**:
  * Disengages follower mode and immediately resumes the 24/7 autonomous floor manager routine.
- **24/7 Autonomous Floor Manager Loop (Every 5 Minutes)**:
  * Runs continuously 24/7 without stopping or waiting for the CEO.
  * **Concurrent Execution**: Both bots are moved together via `asyncio.gather(self.move_bot_to_vc(sadie_client, target_vc_sadie, "Executive Escort 👑"), self.move_bot_to_vc(millie_client, target_vc_millie, "Executive Security 🛡️"), return_exceptions=True)`.
  * **Populated Channel Scanning (No Empty Rooms)**: Dynamically scans the guild for voice channels currently occupied by employees (Team Vaasan bots or active developers). Roaming is strictly restricted to populated channels; if all employee channels are empty, bots standby in `Ceo Vc`.
  * **CEO Presence Detection**: Evaluates if the guild owner OR any human (`member.bot is False`) is inside **Ceo Vc** (`1563622904829190326`):
    - **CEO / Human Inside "Ceo Vc"**:
      * **70% probability**: Both bots stay/move inside "Ceo Vc" with the CEO (Sadie: `Executive Escort 👑`, Millie: `Executive Security 🛡️`).
      * **30% probability**: Move ONLY to populated employee voice channels for floor rounds (NEVER empty rooms).
    - **CEO Absent from "Ceo Vc"** (disconnected, offline, or elsewhere):
      * **20% probability**: Stay in "Ceo Vc" keeping executive office presence.
      * **80% probability**: Roam across populated employee voice channels randomly (NEVER empty rooms).
- **Instant Event Triggers**:
  * When any human joins "Ceo Vc", the system immediately executes the 70/30 roll without waiting 5 minutes.
  * When a human departs "Ceo Vc" leaving it vacant, the system immediately executes the 20/80 roll.
- **Seamless Coexistence**: Runs concurrently with all 5 Team Vaasan bots without interfering with their 24h IST shift schedule.

---

## 📢 Operational Notification Routing Policy

All automated operational notifications and status logs are strictly isolated to ensure clean communication channels:
- **Dedicated CEO Notification Channel**: `yogesh-chat` (Channel ID: `1563622902744481812`)
  * Receives all `/start` and `/stop` company alert embeds.
  * Receives all 24-hour IST shift transition updates (including distributed sleep assignments).
  * Receives live `/status` health and bot presence logs.
- **Clean `#announcements`**: Kept strictly clean and reserved exclusively for manual, high-level corporate announcements posted directly by the CEO.

---

## 🪪 Enterprise Corporate Roles & Digital ID Card Onboarding

The system provisions official enterprise roles and smart digital credentials:
- **Corporate Role Hierarchy**:
  * 👑 `CEO & Founder`: Auto-assigned to the Server Owner (`0xFFD700` Gold).
  * 👔 `Executive Suite`: Assigned to SadieSink & MillieBobbyBrown (`0x9B59B6` Purple).
  * 🧠 `Principal Tech Lead`: Assigned to TTF Vasan & Pradeep Ranganathan (`0x3498DB` Blue).
  * 🎨 `UI/UX Design Lead`: Assigned to Mamitha (`0xE91E63` Magenta).
  * ⚙️ `DevOps & SRE Lead`: Assigned to Kayadu (`0x2ECC71` Green).
  * 🛡️ `InfoSec & QA Lead`: Assigned to Muthazhagi (`0xE67E22` Orange).
  * 💻 `Software Engineer`: Auto-assigned to all human members upon joining (`0x00D2FF` Neon Teal).
  * 🎓 `Engineering Intern`: General support role (`0x95A5A6` Silver).
- **Digital Corporate ID Card (`/idcard` or `!idcard`)**:
  * Automatically issued by **SadieSink** in `#greeting` upon a member's arrival, and viewable anytime via `/idcard [member]`.
  * Embed includes: Full Name, Corporate Serial ID (`VDL-CEO-001` or `VDL-EMP-xxxx`), Department, Designation, Security Clearance Level, Date of Joining, Facility Access Privileges, and Official Authentication Signature.

---

## ☕ Common Pantry & Watercooler Fun (`#cafeteria`)

Simulates genuine IT corporate pantry culture with high-energy Tanglish banter and interactive polls:
- **`/coffee` (or `!coffee`, `!chai`, `!break`)**:
  * Triggers an animated 5-bot coffee break dialogue chain with typing indicators.
  * TTF Vasan hypes the refreshment, Pradeep makes witty bug-fixing jokes, Mamitha critiques cafeteria mug aesthetics, Kayadu monitors calm server loads, and Muthazhagi grants 15-minute QA-approved relaxation tokens!
- **`/pantrydebate [topic]` (or `!pantrydebate`)**:
  * Launches an interactive watercooler debate in `#cafeteria` with **🅰️** vs **🅱️** voting reactions.
  * Includes curated developer topics (*Tabs vs Spaces*, *Vim vs VS Code*, *Dark vs Light Mode*, *Masala Chai vs Filter Coffee*, *WFH vs Office Snacks*, *Frontend vs Backend*).
  * Pradeep and TTF Vasan immediately chime in with hot takes under the voting embed.
- **`/watercooler` (or `!watercooler`, `!snack`)**:
  * Posts the daily corporate snack special (Samosa, Filter Coffee, Masala Maggi, Biscuits) and workplace trivia.
- **Scheduled Rest-Break Notices**:
  * Automatically notifies `#cafeteria` during 24h IST shift breaks (Warmup, Gaming Break, Breakfast, Power Nap, Lunch).

---

## 🚀 Available Commands

| Command | Type | Permissions | Description |
|---|---|---|---|
| `/start` | Slash / `!start` | CEO / Admin | Activates company operations & 24h IST shift scheduler (Alert sent to `#yogesh-chat`) |
| `/stop` | Slash / `!stop` | CEO / Admin | Pauses operations & disconnects all 5 bots from voice (Alert sent to `#yogesh-chat`) |
| `/status` | Slash / `!status` | Everyone | Generates live TTF Vasan status log embed and routes to `#yogesh-chat` |
| `/reset_and_build_server` | Slash / `!reset_and_build_server` | Owner / Admin | Resets server, builds CEO Blueprint & provisions roles (Summary sent to `#yogesh-chat`) |
| `/teamcategory <name>` | Slash / `!teamcategory <name>` | Admin | Duplicates Team Vaasan template for new team |
| `/follow` | Slash / `!follow` | CEO / Admin | SadieSink & MillieBobbyBrown escort CEO in voice |
| `/unfollow` | Slash / `!unfollow` | Everyone | Disconnects bots from voice escort mode |
| `!project <idea>` | Prefix | Everyone | Starts 5-agent Tanglish tech sprint in `#the-launchpad` or `#working-chat` |
| `/idcard [member]` | Slash / `!idcard` | Everyone | Displays official Vaelkry Dev Labs Digital Corporate ID Card |
| `/provision_roles` | Slash / `!provision_roles` | CEO / Admin | Provisions and syncs all 8 enterprise roles across server |
| `/coffee` | Slash / `!coffee` | Everyone | Launches fun 5-agent Tanglish coffee/chai break banter in `#cafeteria` |
| `/pantrydebate [topic]` | Slash / `!pantrydebate` | Everyone | Starts interactive watercooler debate with 🅰️ vs 🅱️ voting |
| `/watercooler` | Slash / `!watercooler` | Everyone | Posts daily pantry snack special & workplace trivia in `#cafeteria` |

---

## 📦 Project Structure

```
vaelkry dev labs/
├── .env                  # Environment variables (7 bot tokens, Gemini key, Guild ID)
├── config.py             # Configuration loader and 7-bot definitions
├── agents.py             # Tanglish developer personas, prompts, and context builders
├── gemini_service.py     # Asynchronous Gemini client with fallback models
├── server_builder.py     # CEO Blueprint builder, role hierarchy, dynamic team scaling
├── moderator_service.py  # Audit logging, greeting cards, digital ID cards, voice follower escort
├── cafeteria_service.py  # Cafeteria coffee breaks, pantry debates, watercooler trivia
├── scheduler_service.py  # Company lifecycle management & 24h IST shift scheduler
├── main.py               # Discord orchestrator running all 7 bots concurrently
├── requirements.txt      # Dependencies (discord.py, google-genai, pynacl, davey, tzdata)
└── README.md             # Documentation
```

---

## ⚡ Running the System

Start all 7 agents concurrently:

```bash
python main.py
```
