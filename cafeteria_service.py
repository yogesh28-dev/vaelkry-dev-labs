"""
Vaelkry Dev Labs - Cafeteria & Watercooler Service
Implements:
1. Interactive Coffee & Chai Break banter with all 5 developer agents (#cafeteria).
2. Live Pantry Debates with 🅰️ vs 🅱️ emoji voting reactions.
3. Workplace Watercooler snack prompts & trivia.
4. Automated rest-break cafeteria notifications synchronized with the 24h IST scheduler.
"""

import asyncio
import logging
import random
from typing import Any, Dict, List, Optional
import discord

logger = logging.getLogger("VaelkryDevLabs.Cafeteria")

# Curated high-energy IT Pantry & Watercooler Debate Topics
PANTRY_DEBATES: List[Dict[str, str]] = [
    {
        "title": "Tabs vs Spaces: The Ultimate Developer War!",
        "topic": "Code indentation-la endha faction mass? Real engineers enna use pannuvaanga?",
        "opt_a": "Tabs (Indentation freedom & clean tabwidth)",
        "opt_b": "Spaces (Strict consistency everywhere, zero rendering mismatch)",
        "pradeep_take": "Spaces use panravanga space-ke poita nalla irukum mapla... Tabs dhaan true freedom!",
        "ttf_take": "Nanba! Indentation pathi pesi time waste panna koodadhu, code 299 km/h speed-la run aagudha-nu paakanum!",
    },
    {
        "title": "Vim vs VS Code: Legendary Hackers vs Modern Wizards!",
        "topic": "Terminal hacker raw speed-ah illa extension paradise full-fledged IDE-ah?",
        "opt_a": "VS Code (IntelliSense, Copilot, rich extensions, zero pain)",
        "opt_b": "Vim / Neovim (Lightning keyboard shortcuts, zero mouse, ultra lightweight)",
        "pradeep_take": "Vim-la enter aana epdi exit aaganum-nu theriyama 3 varusham aachu... VS Code dhaan peace of mind!",
        "ttf_take": "Keyboard shortcut-la bike throttle thirukura maari speed varanum! Vim power vera level!",
    },
    {
        "title": "Dark Mode vs Light Mode: Are Light Mode users human?",
        "topic": "Monitor brightness full-la vechu light mode use panravanga unmaiyaave humans-ah?",
        "opt_a": "Dark Mode (Eyes safe, aesthetic OLED pitch-black contrast)",
        "opt_b": "Light Mode (Daylight readability, paper-like clarity)",
        "pradeep_take": "Light mode on panna retina burn aagi ophthalmologist-kitta dhaan poganum. Dark mode always!",
        "ttf_take": "Night Spend shift-la dark mode illama code adicha eye flash aaidum nanba!",
    },
    {
        "title": "Masala Chai vs Filter Coffee: 3 AM Sprint Oxygen!",
        "topic": "Midnight coding marathon-la bug fix panna ethu real booster?",
        "opt_a": "Kumbakonam Degree Filter Coffee (Thick decoction, instant brain kick)",
        "opt_b": "Irani Masala Chai with Ginger (Warm soul soothing, anti-stress)",
        "pradeep_take": "Coffee illama memory leak debug panna mudiyadhu. Filter coffee is standard dev dependency!",
        "ttf_take": "Masala Chai boost kuduthu adutha commit-ah rocket speed-la push pannuvom!",
    },
    {
        "title": "Work From Home (WFH) vs Office Cafeteria: Comfort vs Free Snacks!",
        "topic": "Bed-la irundhu code panradha illa office pantry-la unlimited coffee & AC-ah?",
        "opt_a": "Work From Home (Zero commute, pyjamas, personal zone)",
        "opt_b": "Office Cafeteria (Free snacks, cafeteria banter, dual monitor setup)",
        "pradeep_take": "Traffic-la maatikura badhila WFH-la sofa-la paduthukitte PR merge pannalaam!",
        "ttf_take": "Office pantry-la ella nanbargalum onna serndhu tea kudichutu sprint adicha adhu dhaan vibe!",
    },
    {
        "title": "Frontend vs Backend: Yaaroda job-la tension athigam?",
        "topic": "Browser rendering CSS pixel alignment-ah illa Production DB deadlocks-ah?",
        "opt_a": "Frontend (CSS overflow, Safari bugs, mobile responsive torture)",
        "opt_b": "Backend (DB deadlock, auth token breach, microservice 500 error)",
        "pradeep_take": "Backend error vandha log paathukalam... CSS center panradhukulla 4 designers sandaiku vandhuruvaanga!",
        "ttf_take": "Rendum onna sendhadhan Vaelkry Dev Labs rocket maari parakum! Both are champions!",
    },
]

# Fun coffee break banter scenarios
COFFEE_SCENARIOS: List[List[Dict[str, str]]] = [
    [
        {
            "bot": "ttf_vasan",
            "text": "Nanba Nanbigale! Coffee & Chai break time! ☕ Cafeteria-ku vaanga! 299 km/h speed-la sprint adichu brain overheat aachu!",
        },
        {
            "bot": "pradeep",
            "text": "Indha NullPointerException-ah debug panna mudiyala-nu coffee machine-oda logic-ah debug panna poren mapla... 'If water==hot then add sugar' nu oru single if condition potrukaan!",
        },
        {
            "bot": "mamitha",
            "text": "Cafeteria cup color palette semmaya iruku! Dark Roast brown with Cream gradient... Figma-la pudhu Vaelkry UI theme ready pannidalam! 🎨✨",
        },
        {
            "bot": "kayadu",
            "text": "Cool-ah irunga pa. Staging server load 8%-la calm-ah run aagudhu. All pipelines green. Arambikka oru ginger tea kudinga.",
        },
        {
            "bot": "muthazhagi",
            "text": "Apdipodu! Break 15 minutes dhaan! Coffee mudinju straight-ah PR security audit-ku vandhurunga, zero vulnerabilities irukanum! 🛡️",
        },
    ],
    [
        {
            "bot": "ttf_vasan",
            "text": "Cafeteria pantry-la hot samosa and chai vanthuruku mapla! Quick energy boost eduthukonga! 🥐⚡",
        },
        {
            "bot": "pradeep",
            "text": "Samosa sapdra speed-la webpack bundle build run aana nalla irukum... bundle size 45MB iruku, adha first optimize pannanum!",
        },
        {
            "bot": "mamitha",
            "text": "Pantry snack counter kooda responsive-ah illaye... plates ellam margin illama overlap aagudhu! Padding kudunga bro! 😂",
        },
        {
            "bot": "kayadu",
            "text": "Docker cache clean panniten. Hot samosa saputu vandhu staging cluster-ku deploy thookuvom.",
        },
        {
            "bot": "muthazhagi",
            "text": "Security Alert: Samosa-la kaaram athigam! All credentials secured, enjoy the refreshment nanba!",
        },
    ],
    [
        {
            "bot": "ttf_vasan",
            "text": "Midnight caffeine squad! Coffee break potu adutha high-speed sprint-ku ready aagiduvom! 🚀☕",
        },
        {
            "bot": "pradeep",
            "text": "Coffee kudichute adicha code dhaan da actual magic... kaalaila paatha code puriyadhu, adhu vera vishayam!",
        },
        {
            "bot": "mamitha",
            "text": "Mood lighting set, warm cappuccino in hand, aesthetic playlist in background. Vaelkry pantry vibe 100/100! ✨",
        },
        {
            "bot": "kayadu",
            "text": "PostgreSQL connection pool healthy-ah iruku. No panic, sit back and enjoy your drink.",
        },
        {
            "bot": "muthazhagi",
            "text": "QA gatekeeper approved: 15-minute relaxation token granted! Drink your coffee peacefully! 🛡️",
        },
    ],
]


def find_cafeteria_channel(guild: discord.Guild) -> Optional[discord.TextChannel]:
    """Finds the #cafeteria channel under Common Pantry."""
    return discord.utils.find(
        lambda ch: ch.name.lower() in ("cafeteria", "common-pantry", "pantry")
        and isinstance(ch, discord.TextChannel),
        guild.text_channels,
    )


class CafeteriaService:
    def __init__(self, orchestrator: Any):
        self.orchestrator = orchestrator
        self.lock = asyncio.Lock()

    async def run_coffee_break(
        self,
        target_channel: discord.abc.Messageable,
        requested_by: Optional[discord.Member] = None,
    ):
        """
        Launches an interactive, rapid-fire Tanglish coffee/chai break banter
        featuring all 5 developer agents in the channel.
        """
        if self.lock.locked():
            await target_channel.send("☕ **Wait panni paaru mapla!** Oru coffee break discussion already live-la iruku! 🔥")
            return

        async with self.lock:
            scenario = random.choice(COFFEE_SCENARIOS)
            requester_mention = requested_by.mention if requested_by else "Team"

            initial_embed = discord.Embed(
                title="☕ VAELKRY DEV LABS — CAFETERIA COFFEE BREAK!",
                description=(
                    f"🔔 **Break announced by {requester_mention}!**\n"
                    f"Team Vaasan is heading to the pantry for fresh refreshments and banter.\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                ),
                color=0xE67E22,
            )
            initial_embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/924/924514.png")
            initial_embed.add_field(
                name="🥐 Pantry Status",
                value="• Masala Chai: Hot & Ready\n• Filter Coffee: Freshly Brewed\n• Snacks: Freshly Stocked",
                inline=False,
            )
            await target_channel.send(embed=initial_embed)

            # Send bot dialogue sequence
            for item in scenario:
                bot_key = item["bot"]
                line = item["text"]
                client = self.orchestrator.clients.get(bot_key)
                if not client:
                    continue

                ch = client.get_channel(target_channel.id) if hasattr(target_channel, "id") else target_channel
                if not ch:
                    continue

                try:
                    await asyncio.sleep(random.uniform(1.2, 2.0))
                    async with ch.typing():
                        await asyncio.sleep(random.uniform(1.0, 1.8))
                        await ch.send(line)
                except Exception as exc:
                    logger.warning(f"Error in coffee banter for {bot_key}: {exc}")

            # Closing banner
            lead_client = self.orchestrator.clients.get("ttf_vasan")
            if lead_client:
                lead_ch = lead_client.get_channel(target_channel.id) if hasattr(target_channel, "id") else target_channel
                if lead_ch:
                    await lead_ch.send(
                        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                        "☕ **Cafeteria Break Concluded!** Refreshment complete. Back to engineering sprint at 299 km/h speed! 🚀"
                    )

    async def start_pantry_debate(
        self,
        target_channel: discord.abc.Messageable,
        custom_topic: Optional[str] = None,
        requested_by: Optional[discord.Member] = None,
    ):
        """
        Starts an interactive IT Watercooler Debate in #cafeteria with 🅰️ vs 🅱️ voting reactions.
        Pradeep and TTF Vasan immediately chime in with hot takes!
        """
        if custom_topic:
            selected_debate = {
                "title": "🔥 Custom Watercooler Debate!",
                "topic": custom_topic,
                "opt_a": "Option A",
                "opt_b": "Option B",
                "pradeep_take": "Mapla, renduthulayum pros and cons iruku, aana practical-ah yosicha thevai illadha complexity!",
                "ttf_take": "Nanba! Decision eduthu udane implement pannunga, speed dhaan mukkiyam!",
            }
        else:
            selected_debate = random.choice(PANTRY_DEBATES)

        requester_str = requested_by.mention if requested_by else "Team"

        embed = discord.Embed(
            title=f"🗣️ PANTRY WATERCOOLER DEBATE: {selected_debate['title']}",
            description=(
                f"**Topic:** *{selected_debate['topic']}*\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"Vote unga opinion-ku keela iruka reactions use panni podunga:\n\n"
                f"🅰️ **{selected_debate['opt_a']}**\n\n"
                f"🅱️ **{selected_debate['opt_b']}**\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            ),
            color=0x3498DB,
        )
        embed.set_footer(text=f"Initiated by {requester_str} • Cast your vote with 🅰️ or 🅱️ below!")

        debate_msg = await target_channel.send(embed=embed)

        # Add initial voting reactions
        try:
            await debate_msg.add_reaction("🅰️")
            await debate_msg.add_reaction("🅱️")
        except Exception as exc:
            logger.warning(f"Failed to add debate reactions: {exc}")

        # Follow-up with Pradeep's sarcastic take and TTF Vasan's hype take
        pradeep_client = self.orchestrator.clients.get("pradeep")
        ttf_client = self.orchestrator.clients.get("ttf_vasan")

        if pradeep_client:
            pradeep_ch = pradeep_client.get_channel(target_channel.id) if hasattr(target_channel, "id") else target_channel
            if pradeep_ch:
                await asyncio.sleep(1.5)
                async with pradeep_ch.typing():
                    await asyncio.sleep(1.5)
                    await pradeep_ch.send(f"**Pradeep:** {selected_debate['pradeep_take']}")

        if ttf_client:
            ttf_ch = ttf_client.get_channel(target_channel.id) if hasattr(target_channel, "id") else target_channel
            if ttf_ch:
                await asyncio.sleep(1.5)
                async with ttf_ch.typing():
                    await asyncio.sleep(1.2)
                    await ttf_ch.send(f"**TTF Vasan:** {selected_debate['ttf_take']}")

    async def post_watercooler_snack(self, target_channel: discord.abc.Messageable):
        """Drops a fun workplace snack trivia or mini-poll in #cafeteria."""
        snack_items = [
            ("Samosa & Green Chutney 🥐", "Crispy hot samosa fresh from corporate pantry"),
            ("Filter Coffee & Medu Vada 🍩", "Classic South Indian tech dev fuel"),
            ("Masala Maggi & Energy Drink 🍜", "3 AM emergency bugfix lifesaver"),
            ("Bournvita Biscuits & Chai 🍪", "Nostalgic 4 PM code review companion"),
            ("Fruit Bowl & Cold Brew 🍎", "Healthy UI/UX designer diet aesthetic"),
        ]
        choice, desc = random.choice(snack_items)

        embed = discord.Embed(
            title="🥐 CAFETERIA PANTRY SPECIAL OF THE DAY!",
            description=(
                f"Today's recommended developer snack:\n\n"
                f"### **{choice}**\n"
                f"*{desc}*\n\n"
                f"React with 😋 if you want a serving delivered to your desk!"
            ),
            color=0xF1C40F,
        )
        msg = await target_channel.send(embed=embed)
        try:
            await msg.add_reaction("😋")
            await msg.add_reaction("❤️")
        except Exception:
            pass

    async def notify_shift_break(self, guild: discord.Guild, shift_name: str, cabin_name: str):
        """Sends an automated rest break notification to #cafeteria."""
        ch = find_cafeteria_channel(guild)
        if not ch:
            return

        lead = self.orchestrator.clients.get("ttf_vasan")
        target_ch = lead.get_channel(ch.id) if lead else ch
        if not target_ch:
            return

        embed = discord.Embed(
            title=f"☕ CAFETERIA NOTICE: {shift_name.upper()} ACTIVE!",
            description=(
                f"Team Vaasan employees have rotated to **{cabin_name}** for scheduled rest!\n\n"
                f"Grab your coffee, tea, and snacks in <#{ch.id}> or hang out in the voice lounge. "
                f"Relax and recharge before the next engineering sprint! 🥐🎮"
            ),
            color=0x2ECC71,
        )
        embed.set_footer(text="Vaelkry Dev Labs Enterprise Routine • Work-Life Balance Policy")
        try:
            await target_ch.send(embed=embed)
        except Exception as exc:
            logger.warning(f"Failed to send cafeteria shift break notice: {exc}")
