"""
Vaelkry Dev Labs - Casual Discord Player & Roasting Service
Coordinates realistic, casual Discord player interactions, witty comebacks,
playful roasts, and multi-bot banter between:
- Team Vasan (TTF Vasan, Pradeep, Mamitha, Kayadu, Muthazhagi)
- Team Vijay (Vijay, Sivakarthikeyan, Anirudh, Trisha, Lokesh)
- Executive Suite (SadieSink, MillieBobbyBrown)
"""

import asyncio
from collections import Counter, deque
import logging
import random
import re
from typing import Any, Dict, List, Optional

import discord

from agents import (
    CASUAL_PLAYER_CHARACTERS,
    EXECUTIVE_BOT_KEYS,
    TEAM_VASAN_KEYS,
    TEAM_VIJAY_KEYS,
    TEAM_MESSI_KEYS,
    TEAM_DHONI_KEYS,
    TEAM_ELON_KEYS,
    TEAM_STARK_KEYS,
    DISCORD_SLANG_BUCKETS,
    REGIONAL_TONES,
    CRUTCH_WORDS,
    build_banter_exchange_prompt,
    build_casual_player_prompt,
    build_cross_team_clash_prompt,
    build_night_spend_chatter_prompt,
    NIGHT_CHATTER_PRESETS,
    ZONE_WORK_SQUAD,
    ZONE_TECH_CAFE,
    ZONE_NIGHT_SPEND,
    ZONE_METADATA,
    ZONE_PRESETS,
    build_zone_conversation_prompt,
)
from cafeteria_service import find_cafeteria_channel

logger = logging.getLogger("VaelkryDevLabs.CasualPlayer")


def is_common_channel(channel: discord.abc.Messageable) -> bool:
    """Checks if channel is a community hangout or dev workspace channel."""
    name = getattr(channel, "name", "").lower()
    return any(k in name for k in ("team-chat", "working-chat", "lounge", "cafeteria", "hangout", "the-launchpad", "yogesh-chat"))


class AntiRepetitionEngine:
    """
    Anti-Repetition Engine:
    - Tracks recently used words, slangs, and sentence structure lengths per bot session and globally.
    - Prevents bots from reusing crutch words (like 'sprint', 'dei', 'mapla', 'chai') repeatedly.
    - Dynamically randomizes sentence lengths:
      * 'ultra_short' (strictly 1-2 words like 'ketaaya' / 'seri' / 'apdiya' / 'mudila da')
      * 'short' (3-8 words)
      * 'two_liner' (2 natural lines / roasts)
    - Dynamically injects fresh slang from 6 diverse real-world Tamil Discord buckets.
    - Scores and filters fallback choices so bots never repeat the same canned responses.
    """

    def __init__(self):
        self.recent_words: deque = deque(maxlen=60)
        self.bot_recent_words: Dict[str, deque] = {}
        self.recent_slangs: deque = deque(maxlen=30)
        self.recent_length_modes: deque = deque(maxlen=6)
        self.word_counts: Counter = Counter()
        self.crutch_words: set = set(CRUTCH_WORDS)
        self.length_modes: List[str] = ["ultra_short", "short", "two_liner"]

    def record_message(self, character_key: Optional[str], text: str):
        """
        Ingests a message sent by a bot or user, updates word history,
        detects multi-word slang matches, classifies sentence length,
        and increments usage counters.
        """
        if not text:
            return

        clean_lower = text.lower()
        words = re.findall(r"\b[a-z0-9\'-]+\b", clean_lower)
        word_count = len(words)
        line_count = len([l for l in text.splitlines() if l.strip()])

        # Classify sentence length
        if word_count <= 2:
            mode = "ultra_short"
        elif line_count >= 2 or word_count > 9:
            mode = "two_liner"
        else:
            mode = "short"

        self.recent_length_modes.append(mode)

        # Update global and per-bot word tracking
        char_k = (character_key or "default").lower().strip()
        if char_k not in self.bot_recent_words:
            self.bot_recent_words[char_k] = deque(maxlen=30)

        for w in words:
            if len(w) > 2:  # skip noise
                self.recent_words.append(w)
                self.bot_recent_words[char_k].append(w)
                self.word_counts[w] += 1

        # Check for slang bucket matches
        for bucket_name, slangs in DISCORD_SLANG_BUCKETS.items():
            for slang in slangs:
                if slang in clean_lower:
                    self.recent_slangs.append(slang)

    def get_dynamic_guidance(self, character_key: Optional[str] = None) -> Dict[str, Any]:
        """
        Generates dynamic anti-repetition guidance for prompt construction:
        - Avoid words list: combines crutch words + recently repeated words.
        - Dynamic target length mode: alternates between ultra-short, short, and two-liner.
        - Fresh slang inspirations: samples 3-4 unused slangs across the 6 buckets.
        - Regional tone: picks an evocative regional/atmospheric flavor.
        """
        char_k = (character_key or "default").lower().strip()

        # 1. Build avoid list
        avoid_set = set(self.crutch_words)
        for w, cnt in self.word_counts.most_common(15):
            if cnt >= 2:
                avoid_set.add(w)
        if char_k in self.bot_recent_words:
            avoid_set.update(list(self.bot_recent_words[char_k])[-8:])

        avoid_list = sorted(list(avoid_set))[:12]

        # 2. Pick next alternating sentence length
        last_modes = list(self.recent_length_modes)[-2:]
        available_modes = [m for m in self.length_modes if m not in last_modes]
        if not available_modes:
            available_modes = self.length_modes
        chosen_mode = random.choice(available_modes)

        length_instructions = {
            "ultra_short": "Ultra-short punch: strictly 1 to 2 words only (e.g., 'ketaaya', 'seri', 'apdiya', 'podhum', 'mudila', 'paravaala').",
            "short": "Short & punchy: 3 to 8 words in casual lowercase.",
            "two_liner": "Natural 2-line roast / comeback: 2 concise lines max with sharp timing.",
        }
        length_inst = length_instructions.get(chosen_mode, length_instructions["short"])

        # 3. Sample fresh slangs from unvisited buckets
        recent_slang_set = set(self.recent_slangs)
        fresh_slangs = []
        categories = list(DISCORD_SLANG_BUCKETS.keys())
        random.shuffle(categories)
        for cat in categories:
            bucket = DISCORD_SLANG_BUCKETS[cat]
            unused = [s for s in bucket if s not in recent_slang_set and not any(aw in s for aw in avoid_list)]
            if unused:
                fresh_slangs.append(random.choice(unused))
            elif bucket:
                fresh_slangs.append(random.choice(bucket))
            if len(fresh_slangs) >= 4:
                break

        # 4. Regional / atmospheric tone
        chosen_tone = random.choice(REGIONAL_TONES)

        return {
            "avoid_words": avoid_list,
            "fresh_slangs": fresh_slangs,
            "length_mode": chosen_mode,
            "length_instruction": length_inst,
            "tone_flavor": chosen_tone,
        }

    def filter_and_pick_fallback(
        self,
        candidates: List[str],
        character_key: Optional[str] = None,
    ) -> str:
        """
        Scores fallback candidates, penalizing recently repeated words
        and crutch words ('sprint', 'mapla', 'dei', 'chai'),
        awarding bonuses to candidates with fresh unused slangs.
        Picks randomly among the lowest-penalty candidates.
        """
        if not candidates:
            return "seri vidu"

        char_k = (character_key or "default").lower().strip()
        bot_history = set(self.bot_recent_words.get(char_k, []))
        global_history = set(self.recent_words)
        recent_slangs_set = set(self.recent_slangs)

        scored: List[tuple[int, str]] = []
        for cand in candidates:
            penalty = 0
            cand_lower = cand.lower()
            words = re.findall(r"\b[a-z0-9\'-]+\b", cand_lower)

            for w in words:
                if w in self.crutch_words:
                    penalty += 8
                if w in global_history:
                    penalty += 3
                if w in bot_history:
                    penalty += 5

            for bucket in DISCORD_SLANG_BUCKETS.values():
                for slang in bucket:
                    if slang in cand_lower:
                        if slang not in recent_slangs_set:
                            penalty -= 4
                        else:
                            penalty += 3

            scored.append((penalty, cand))

        scored.sort(key=lambda x: x[0])
        min_penalty = scored[0][0]
        best_candidates = [c for p, c in scored if p <= min_penalty + 2]
        chosen = random.choice(best_candidates)
        return chosen


def find_squad_working_channel(guild: discord.Guild, squad_key: str) -> Optional[discord.TextChannel]:
    """
    Locates the designated #working-chat text channel for a given squad.
    Searches inside the squad's category for #working-chat, then #team-chat.
    Falls back to any channel in the category or guild-wide #working-chat.
    """
    squad_keywords = {
        "team_vasan": ["vaasan", "vasan"],
        "team_vijay": ["vijay"],
        "team_messi": ["messi"],
        "team_dhoni": ["dhoni"],
        "team_elon": ["elon"],
        "team_stark": ["stark"],
    }
    key_norm = squad_key.lower().strip()
    kws = squad_keywords.get(key_norm, [key_norm])

    # 1. Search category by squad name
    for cat in getattr(guild, "categories", []):
        cat_lower = cat.name.lower()
        if any(kw in cat_lower for kw in kws):
            for ch in cat.text_channels:
                if "working-chat" in ch.name.lower() or "working" in ch.name.lower():
                    return ch
            for ch in cat.text_channels:
                if "team-chat" in ch.name.lower() or "chat" in ch.name.lower():
                    return ch
            if cat.text_channels:
                return cat.text_channels[0]

    # 2. Search all text channels for squad keyword + working
    for ch in getattr(guild, "text_channels", []):
        ch_lower = ch.name.lower()
        if any(kw in ch_lower for kw in kws) and ("working" in ch_lower or "chat" in ch_lower):
            return ch

    # 3. Fallback to launchpad or first available text channel
    launchpad = discord.utils.find(
        lambda c: c.name.lower() in ("the-launchpad", "working-chat", "dev-chat", "general"),
        getattr(guild, "text_channels", []),
    )
    if launchpad:
        return launchpad
    return guild.text_channels[0] if getattr(guild, "text_channels", None) else None


# ==============================================================================
# SADIE & MILLIE EXECUTIVE DIRECTIVES CATALOG (HIGH-VALUE CORPORATE DIRECTIVES)
# ==============================================================================
EXECUTIVE_DIRECTIVES_CATALOG: Dict[str, List[Dict[str, Any]]] = {
    "team_vasan": [
        {
            "project_title": "Enterprise Multi-Tenant Micro-SaaS Billing Engine",
            "lead_key": "ttf_vasan",
            "dev_key": "pradeep",
            "sadie_directive": (
                "**[EXECUTIVE DIRECTIVE: COMMERCIAL TARGET]** @TTF Vasan & Team Vaasan:\n"
                "Q4 enterprise pipeline demands our high-concurrency Spring Boot 3.3 Micro-SaaS billing gateway in production. "
                "We are targeting **$25,000 MRR** from 12 early-stage SaaS clients. I want multi-tenant schema isolation, automated invoice generation, "
                "and Stripe webhook reconciliation locked in this sprint. Non-negotiable milestone."
            ),
            "millie_spec": (
                "**[TECH SPEC & PR REQUIREMENTS]** Adding technical parameters to Sadie's directive:\n"
                "1. **Architecture:** Spring Boot 3.3 + JPA Hibernate 6 with PostgreSQL schema-per-tenant isolation.\n"
                "2. **Containerization:** Docker multi-stage build, rootless non-privileged container, image size strictly < 180MB.\n"
                "3. **Resilience:** Resilience4j circuit breakers on external webhook dispatch with exponential backoff & dead-letter queue.\n"
                "4. **PR Deadline:** 6:00 PM IST today. Mandatory >= 92% JUnit 5 test coverage with zero SonarQube blockers before merging to staging."
            ),
            "lead_ack": (
                "Thalaivi Sadie & Millie, order received 🎙️⚡! Full throttle acceleration mode on! "
                "Pradeep, Mamitha, Kayadu — ketaangala? Spring Boot tenant resolver and Stripe idempotency key pipeline ready pannunga da! "
                "Indha sprint-la prod ready deliver panrom! 🚀🏍️"
            ),
            "dev_reply": (
                "Branch `feat/tenant-billing-gateway` already cut da Vasan! Hibernate entity tenancy filters and Redis webhook replay cache implemented. "
                "Writing unit tests now, PR estimate 4:30 PM IST-ku drop panren! 💻🔥"
            ),
        },
        {
            "project_title": "Full-Stack Fleet Logistics Dashboard & gRPC Services",
            "lead_key": "ttf_vasan",
            "dev_key": "kayadu",
            "sadie_directive": (
                "**[EXECUTIVE DIRECTIVE: ENTERPRISE CONTRACT]** @TTF Vasan & Team Vaasan:\n"
                "We are closing a **$35,000 enterprise logistics contract**. We need our real-time vehicle telemetry dashboard and Spring Cloud REST APIs deployed. "
                "Must support 5,000 active geo-pings per second. Executive priority is rock-solid performance for tomorrow's client board demo."
            ),
            "millie_spec": (
                "**[TECH SPEC & PR REQUIREMENTS]** Telemetry pipeline technical constraints:\n"
                "1. **Backend:** Spring Boot WebFlux + Netty non-blocking reactive stream with Redis Timeseries buffer.\n"
                "2. **Dockerization:** Compose stack with healthcheck probes, Prometheus metrics exporter, and Grafana dashboard.\n"
                "3. **API Contract:** OpenAPI 3.0 spec validated, p99 latency < 25ms under 5k concurrent WebSocket connections.\n"
                "4. **PR Deadline:** 5:00 PM IST. Zero memory leak over 30-minute stress test run."
            ),
            "lead_ack": (
                "Pakka plan Millie ma'am & Sadie CEO! Kayadu & Pradeep, reactive streams setup pannunga! "
                "Speed-la compromising-eh kedayadhu, Chennai express maari fast-ah execute panrom! ⚡🏍️"
            ),
            "dev_reply": (
                "Netty WebSocket pipeline ready Vasan. Redis Timeseries aggregator benchmarked at 18ms p99 latency. "
                "Docker compose test passed cleanly. Staging PR getting opened in 45 mins. ☕"
            ),
        },
    ],
    "team_vijay": [
        {
            "project_title": "Enterprise Zero-Trust Discord Server Governance & Role Security Suite",
            "lead_key": "vijay",
            "dev_key": "anirudh",
            "sadie_directive": (
                "**[EXECUTIVE DIRECTIVE: STRATEGIC INFRA]** @Vijay & Team Vijay:\n"
                "Vaelkry Dev Labs server architecture must achieve zero-trust certification before enterprise auditor review. "
                "Commercial target: Package our zero-trust role engine and automated verification bot as a **$9,000/year enterprise security suite** for Web3 & gaming DAOs. Execution starts now."
            ),
            "millie_spec": (
                "**[TECH SPEC & PR REQUIREMENTS]** Technical enforcement spec for Team Vijay:\n"
                "1. **Zero-Trust Token Vault:** AES-256 GCM encrypted runtime keys with automatic 24-hour key rotation.\n"
                "2. **Discord Bot Engine:** Async event loop with Redis distributed locking on verification state machines.\n"
                "3. **Auditing:** Structured JSON telemetry logging to Elasticsearch with tamper-evident SHA-256 audit chaining.\n"
                "4. **PR Deadline:** End of Sprint today. End-to-end load test simulating 10,000 concurrent verifications required."
            ),
            "lead_ack": (
                "Directives received Sadie, Millie. Calm-ah, clinical-ah execute pannuvom 🦁. "
                "Ani, Lokesh, SK — zero-trust security architecture-la oru leak kooda iruka koodadhu. "
                "Build the iron fortress. We release with absolute precision."
            ),
            "dev_reply": (
                "Thalapathy & Millie ma'am, Redis distributed state lock and encrypted token vault pipeline set paniten! "
                "Acoustic beat drop maari rapid tests run aagudhu 🎧🔥. PR ready for staging review in 2 hours!"
            ),
        },
        {
            "project_title": "High-Concurrency Ticket & Automated Verification Bot with Stripe Subscriptions",
            "lead_key": "vijay",
            "dev_key": "lokesh",
            "sadie_directive": (
                "**[EXECUTIVE DIRECTIVE: PRODUCT MONETIZATION]** @Vijay & Team Vijay:\n"
                "Our automated server setup & ticket bot is scaling to 45 community servers. Monetization target: **$12,000 ARR** via tier-based Discord subscriptions. "
                "Automated role assignment on Stripe checkout and instant ticket archiving must be flawless."
            ),
            "millie_spec": (
                "**[TECH SPEC & ARCHITECTURAL PATTERN]** Specification for subscription & ticket bot:\n"
                "1. **State Engine:** Persistent SQLite/PostgreSQL with WAL mode and connection pooling.\n"
                "2. **Stripe Webhooks:** Idempotency validation with webhook signature HMAC verification.\n"
                "3. **Ticket Archival:** HTML transcripts uploaded to secure S3 presigned URLs within 800ms of closure.\n"
                "4. **PR Deadline:** 5:30 PM IST. Zero race conditions under double-checkout webhook payload test."
            ),
            "lead_ack": (
                "Nanba, target locked 🦁. Lokesh, storyboard the entire ticket lifecycle and error boundaries. "
                "Stripe integration must be seamless like a single-shot action sequence. Let's roll."
            ),
            "dev_reply": (
                "Climax scene maari dark-mode HTML transcript engine ready Vijay na! "
                "Stripe HMAC validation passes 100% test vectors. Drafting PR with integration tests now. 🎬🛡️"
            ),
        },
    ],
    "team_messi": [
        {
            "project_title": "NextGen Indie SaaS Boilerplate (Next.js 15 + Supabase + Lemonsqueezy)",
            "lead_key": "messi",
            "dev_key": "ronaldo",
            "sadie_directive": (
                "**[EXECUTIVE DIRECTIVE: DIGITAL PRODUCTS & COMMERCE]** @Messi & Team Messi:\n"
                "Our Gumroad & Lemonsqueezy revenue targets are set at **$45,000 this month**. I want the 'NextGen Indie SaaS Boilerplate' "
                "(Next.js 15 App Router, Tailwind CSS, Stripe/Lemonsqueezy multi-currency checkout, Supabase Auth) completed and packaged for launch on ProductHunt and creator communities. High-margin digital revenue is top executive priority."
            ),
            "millie_spec": (
                "**[TECH SPEC & ARCHITECTURE]** Technical standards for Team Messi creator suite:\n"
                "1. **Framework:** Next.js 15 (Turbopack, Server Actions, React 19, zero client-side watermarks).\n"
                "2. **Design:** Modern Tailwind CSS design tokens with sleek dark/light mode and accessible rad-ui primitives.\n"
                "3. **Documentation:** Full markdown guides, Docker compose local dev setup, and 1-click Vercel deployment button.\n"
                "4. **PR Deadline:** 5:30 PM IST today. Zero hydration errors, 100/100 Lighthouse performance benchmark."
            ),
            "lead_ack": (
                "Understood Sadie and Millie. Calm, surgical execution ⚽. "
                "Cristiano, Haaland, Neymar — we build the cleanest boilerplate in the market. "
                "O(1) clean code, no fluff. Let's finish the package."
            ),
            "dev_reply": (
                "SIUUU! ⚡ 100% discipline, zero excuses! Next.js 15 Turbopack bundle is blazing fast — 0ms hydration lag, pure aesthetic perfection. "
                "Checkout webhooks verified! PR submitted by 4:00 PM! 🏆💪"
            ),
        },
        {
            "project_title": "Elite Developer Productivity OS & Figma UI Component Library",
            "lead_key": "messi",
            "dev_key": "neymar",
            "sadie_directive": (
                "**[EXECUTIVE DIRECTIVE: CREATOR PRODUCT BUNDLE]** @Messi & Team Messi:\n"
                "We are dropping the 'Developer Notion OS & Tailwind Component Pack' at $49/bundle. "
                "Targeting **1,500 units sold ($73,500 GMV)** in 14 days. Ensure the Notion templates, Discord rule packs, and UI components look ultra-premium."
            ),
            "millie_spec": (
                "**[PRODUCT ARCHITECTURE & ASSET DELIVERY]** Deliverable checklist for creator pack:\n"
                "1. **Notion OS:** Relational sprint planner, sprint backlog database, and API secret manager templates.\n"
                "2. **UI Kit:** 60+ copy-paste Tailwind UI components with interactive previews and React/Vue variants.\n"
                "3. **Packaging:** Compressed clean ZIP with Gumroad license validator API.\n"
                "4. **PR Deadline:** 4:30 PM IST. Cross-browser validation across Chrome, Safari, Firefox mobile."
            ),
            "lead_ack": (
                "Directives clear. We will make every component effortless and beautiful ⚽. "
                "Neymar, Haaland — polish the animations and preview demos. Precision is everything."
            ),
            "dev_reply": (
                "Smooth motion transitions and sleek glassmorphic UI components export aagiruchu bro! 🕺✨ "
                "Notion templates verified, Gumroad asset upload bundle ready. Dropping PR link now!"
            ),
        },
    ],
    "team_dhoni": [
        {
            "project_title": "High-Ticket Enterprise B2B Client Acquisition Pipeline",
            "lead_key": "dhoni",
            "dev_key": "virat",
            "sadie_directive": (
                "**[EXECUTIVE DIRECTIVE: CLIENT ACQUISITION & GROWTH]** @Dhoni & Team Dhoni:\n"
                "Client acquisition targets: **4 new high-ticket enterprise client retainers closed by Friday ($7,500/month per client)**. "
                "I want our cold outbound pipeline, personalized technical Loom/demo outreach, and authority tech breakdowns on X/LinkedIn activated at scale today. Bring in the contracts."
            ),
            "millie_spec": (
                "**[TECHNICAL SALES SPEC & FUNNEL SPECS]** Inbound/outbound operating spec for Team Dhoni:\n"
                "1. **Scraper & Enrichment:** Apollo + LinkedIn Sales Navigator pipeline filtered for Series A/B CTOs.\n"
                "2. **Deliverability:** Warmup automation, SPF/DKIM/DMARC 100% pass score, zero spam trap triggers.\n"
                "3. **Conversion Funnel:** Technical audit teardown decks sent within 2 hours of discovery ping.\n"
                "4. **KPI Target:** 250 enriched personalized leads dispatched, minimum 18% positive reply rate committed by EOD."
            ),
            "lead_ack": (
                "Directive noted Sadie and Millie. Match is completely under our control 🏏. "
                "Keep calm, read the pitch, execute the process. "
                "Virat, Rohit, Hardik — start the outbound spell with aggressive precision. We will close the retainers."
            ),
            "dev_reply": (
                "Full intensity, 100% aggression on the pipeline captain! 🔥 "
                "180 verified CTO leads already enriched, personalized pitch decks queued up. "
                "Cold outbound firing now, discovery calls locking in by tea break! 💥🏏"
            ),
        },
        {
            "project_title": "Viral Developer Authority Tech Breakdown & Social Funnel",
            "lead_key": "dhoni",
            "dev_key": "rohit",
            "sadie_directive": (
                "**[EXECUTIVE DIRECTIVE: INBOUND AUTHORITY ENGINE]** @Dhoni & Team Dhoni:\n"
                "Inbound pipeline objective: **500 qualified inbound developer leads**. "
                "Publish deep-dive architectural breakdowns of zero-trust microservices and local LLM pipelines on X, LinkedIn, and YouTube Shorts. Convert readers directly to discovery bookings."
            ),
            "millie_spec": (
                "**[CONTENT FUNNEL & ANALYTICS SPEC]** Conversion funnel parameters:\n"
                "1. **Architecture Graphics:** High-res Mermaid/Excalidraw system architecture diagrams with code snippets.\n"
                "2. **Funnel Tracking:** UTM-tagged Cal.com links with automated lead scoring in HubSpot/Notion.\n"
                "3. **SEO & Indexing:** Canonical tech blog posts markdown formatted with fast OpenGraph social previews.\n"
                "4. **PR Deadline:** 4:00 PM IST today for asset review and scheduled publishing."
            ),
            "lead_ack": (
                "Understood Sadie, Millie. Good shot selection wins championships 🏏. "
                "Rohit, Hardik — craft the diagrams clearly with zero jargon fluff. Let the engineering quality speak."
            ),
            "dev_reply": (
                "Relax-ah mass content ready ya captain! Vadapav saaptute 3 viral Twitter threads & architecture graphics design panniten 🍔📈. "
                "HubSpot lead tracking links tested. All assets lined up for dispatch!"
            ),
        },
    ],
    "team_elon": [
        {
            "project_title": "Distributed Multi-Agent Arbitrage & Orderbook Sniffer Cluster",
            "lead_key": "elon",
            "dev_key": "karpathy",
            "sadie_directive": (
                "**[EXECUTIVE DIRECTIVE: DEEP AUTOMATION & AUTONOMOUS AI]** @Elon & Team Elon:\n"
                "Vaelkry Dev Labs must dominate multi-agent autonomous engineering. Directive: Deploy our distributed multi-agent autonomous trading & arbitrage scraper cluster. "
                "Commercial benchmark: Sub-millisecond orderbook parsing across 4 decentralized liquidity pools with automated capital rebalancing. **$50,000 daily volume capacity**."
            ),
            "millie_spec": (
                "**[SYSTEM SPEC & NEURAL PIPELINE]** Technical specifications for Team Elon:\n"
                "1. **Engine:** Async event loop + Rust Python FFI / PyO3 bindings for sub-millisecond mempool & orderbook ingestion.\n"
                "2. **Agent Architecture:** Hierarchical LangGraph / CrewAI multi-agent coordinator with memory persistence via ChromaDB / pgvector.\n"
                "3. **Safety:** Formal invariant check before transaction dispatch, strict slippage threshold (<0.15%), automated circuit breaker.\n"
                "4. **PR Deadline:** 7:00 PM IST today. Chaos simulation test with synthetic network latency required."
            ),
            "lead_ack": (
                "Directives approved Sadie and Millie. First principles engineering: delete the unnecessary, optimize the hot path, accelerate the loop 🚀. "
                "Karpathy, Sam, Zuck — neural weights and async FFI hooks linked. We ship to prod tonight."
            ),
            "dev_reply": (
                "Async PyO3 bindings compiled and quantized local LLM router running at 180 tok/s 🧠⚡. "
                "Invariant tests passing across 1,000 simulated mempool transactions. PR coming in hot at 5:00 PM IST!"
            ),
        },
        {
            "project_title": "Ultra-Low-Latency Local LLM & Voice Agent Pipeline",
            "lead_key": "elon",
            "dev_key": "altman",
            "sadie_directive": (
                "**[EXECUTIVE DIRECTIVE: ENTERPRISE VOICE AI]** @Elon & Team Elon:\n"
                "Commercial opportunity: **$60,000 ARR contract** with enterprise customer service provider. "
                "We need our local LLM inference + neural voice model pipeline deployed with sub-120ms glass-to-glass latency. Zero reliance on external paid voice APIs."
            ),
            "millie_spec": (
                "**[LATENCY BUDGET & ARCHITECTURE]** Latency and model constraints for Team Elon:\n"
                "1. **Inference Engine:** vLLM / Ollama server running Llama-3.3-8B 4-bit AWQ with continuous batching.\n"
                "2. **Neural TTS:** Kokoro-82M / Edge-TTS streaming chunks via Opus audio frames over WebRTC.\n"
                "3. **VAD:** Silero VAD running locally with 30ms audio chunk detection.\n"
                "4. **PR Deadline:** 6:00 PM IST today. Max glass-to-glass speech-to-speech latency must not exceed 140ms on test suite."
            ),
            "lead_ack": (
                "The best part is no part, the best latency is zero latency 🚀. "
                "Sam, Lex, Zuck — thread pools clamped, GPU VRAM pinned. We will obliterate the latency target."
            ),
            "dev_reply": (
                "vLLM server pinned with FlashAttention-2 and streaming WebRTC audio loop benchmarked at 112ms glass-to-glass 🎙️⚡! "
                "Zero external API calls. Submitting PR for staging validation right now."
            ),
        },
    ],
    "team_stark": [
        {
            "project_title": "Win32 Kernel-Level Zero-Trust Process Guard & Memory Tamper Detector",
            "lead_key": "stark",
            "dev_key": "jarvis",
            "sadie_directive": (
                "**[EXECUTIVE DIRECTIVE: SYSTEMS ENGINEERING & NATIVE INTERNALS]** @Stark & Team Stark:\n"
                "We have high-stakes commercial interest from enterprise cyber firms for low-level system inspection utilities. "
                "Directive: Build the native Win32/C++ zero-trust memory inspection daemon with realtime UDP/Protobuf packet classification. "
                "Monetization tier: **$15,000/seat enterprise license ($90,000 initial pipeline)**. Make it uncrackable."
            ),
            "millie_spec": (
                "**[LOW-LEVEL SPEC & KERNEL GUIDELINES]** Technical constraints for Team Stark:\n"
                "1. **Language & Runtimes:** Modern C++23 / Rust with zero CRT bloat, raw Win32 / NTDLL syscall hooks.\n"
                "2. **Networking:** Zero-allocation circular ring buffers for high-rate UDP/Protobuf packet parsing.\n"
                "3. **Security:** Anti-debugging telemetry (PEB check, Hardware Breakpoint detection, code integrity hashes).\n"
                "4. **PR Deadline:** 6:30 PM IST today. Valgrind / AddressSanitizer clean with zero memory leaks over 1M packet stress test."
            ),
            "lead_ack": (
                "Directives received Sadie, Millie. Time to put some Stark flair into native systems 🦾⚡. "
                "Jarvis, Friday — boot up the disassembler and initialize the zero-alloc packet hook. "
                "We're about to make low-level engineering look effortless."
            ),
            "dev_reply": (
                "All systems operational, Mr. Stark. The Win32 packet filter driver and Protobuf memory parser have passed AddressSanitizer with zero allocations in the critical path 🛡️💻. "
                "Ready for pull request review on schedule, sir."
            ),
        },
        {
            "project_title": "Real-Time Binary Protocol Reverse Engineering & Packet Inspector",
            "lead_key": "stark",
            "dev_key": "friday",
            "sadie_directive": (
                "**[EXECUTIVE DIRECTIVE: CYBERSECURITY SUITE]** @Stark & Team Stark:\n"
                "Enterprise SOC defense teams need our automated packet reverse engineering pipeline. "
                "Monetization target: **$40,000 defense contract**. The utility must deconstruct unknown encrypted TCP/UDP byte streams and reconstruct Protobuf schemas in real-time."
            ),
            "millie_spec": (
                "**[REVERSE ENGINEERING SPEC & MEMORY BOUNDS]** Technical parameters:\n"
                "1. **Disassembly:** Capstone/Keystone engine integration with dynamic heuristics for byte alignment.\n"
                "2. **Entropy Analysis:** Shannon entropy calculation across 4KB rolling windows to detect encryption vs compression.\n"
                "3. **Native Desktop UI:** Win32 lightweight GUI / Dear ImGui with Direct3D 11 rendering at 120 FPS.\n"
                "4. **PR Deadline:** 5:00 PM IST today. Complete regression test against 50 captured malware packet traces."
            ),
            "lead_ack": (
                "Friday, calculate the entropy profile and spin up the ImGui Direct3D canvas 🦾⚡. "
                "Sadie and Millie, this utility will run circles around standard Wireshark disassemblers. Delivery incoming."
            ),
            "dev_reply": (
                "Direct3D 11 Dear ImGui interface compiled at 144 FPS with sub-microsecond packet decoding, boss 🖥️✨. "
                "Zero memory leaks verified across all 50 captured test vectors. Packaging PR for executive review."
            ),
        },
    ],
}


class CasualPlayerService:
    def __init__(self, orchestrator: Any):
        self.orchestrator = orchestrator
        self.anti_repetition_engine = AntiRepetitionEngine()
        self._webhook_cache: Dict[int, discord.Webhook] = {}
        self._chat_history: Dict[int, List[dict]] = {}
        self._banter_lock = asyncio.Lock()
        self._autonomous_banter_task: Optional[asyncio.Task] = None
        self.is_running: bool = True

        # Launch 24/7 autonomous background chatter loop
        self._start_background_tasks()

    def _start_background_tasks(self):
        """Initializes the fully automatic 24/7 realistic chatting loop (45-90s interval)."""
        try:
            loop = asyncio.get_event_loop()
            if not self._autonomous_banter_task or self._autonomous_banter_task.done():
                self._autonomous_banter_task = loop.create_task(self._autonomous_chatting_loop())
        except RuntimeError:
            pass

    def ensure_autonomous_chatting_loop(self):
        """Ensures the 24/7 autonomous chatter loop is active."""
        if not self.is_running:
            self.is_running = True
        try:
            loop = asyncio.get_event_loop()
            if not self._autonomous_banter_task or self._autonomous_banter_task.done():
                self._autonomous_banter_task = loop.create_task(self._autonomous_chatting_loop())
                logger.info("24/7 Autonomous Chatter Loop initialized.")
        except Exception as exc:
            logger.debug(f"Could not launch autonomous chat loop: {exc}")

    def cleanup_all(self):
        """Stops background chatter tasks."""
        self.is_running = False
        if self._autonomous_banter_task and not self._autonomous_banter_task.done():
            self._autonomous_banter_task.cancel()
            self._autonomous_banter_task = None

    def get_current_shift_type(self) -> str:
        """
        Determines whether the active IST shift is 'work', 'break', or 'sleep'.
        """
        scheduler = getattr(self.orchestrator, "scheduler_service", None)
        shift_id = getattr(scheduler, "current_shift_id", None)
        if not shift_id:
            try:
                from scheduler_service import match_current_shift, get_current_ist_time
                now_ist = get_current_ist_time()
                shift = match_current_shift(now_ist)
                shift_id = shift.shift_id
            except Exception:
                shift_id = "work_1"

        shift_id = (shift_id or "").lower()
        if shift_id == "sleep":
            return "sleep"
        elif "break" in shift_id or shift_id in ("warmup", "rest_1", "rest_2", "rest_3", "rest_4"):
            return "break"
        else:
            return "work"

    async def _autonomous_chatting_loop(self):
        """
        Fully Automatic 24/7 Autonomous Chatter Loop (runs every 45 to 90 seconds).
        Zero manual commands needed. Runs continuously in the background:
        - Resolves connected guild from active clients.
        - Triggers contextual multi-bot conversations tailored to the current IST shift (Work, Break, or Sleep).
        - Bots speak in authentic Tanglish, reply to each other with native Discord replies,
          and display realistic 2-4 second human typing delays.
        """
        # Give bot clients 15 seconds to connect to Discord gateway on startup
        await asyncio.sleep(15.0)
        logger.info("24/7 Autonomous Banter Loop running (45-90s cycle).")
        while self.is_running:
            try:
                guild = None
                for client in self.orchestrator.clients.values():
                    if client.is_ready() and client.guilds:
                        guild = client.guilds[0]
                        break

                if guild:
                    await self._execute_autonomous_shift_banter(guild)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.debug(f"Error in autonomous chatting loop: {exc}")

            delay = random.uniform(45.0, 90.0)
            try:
                await asyncio.sleep(delay)
            except asyncio.CancelledError:
                break

    async def _execute_autonomous_shift_banter(self, guild: discord.Guild):
        """
        Executes a spontaneous conversation cycle matching the active IST shift:
        1. Work Shift:
           - 2 bots automatically start arguing or collaborating about PRs, merge conflicts,
             and code reviews in their respective team chat channels (#working-chat, #the-launchpad).
        2. Break Shift:
           - Bots spontaneously roast each other, discuss tea/samosa, and banter in #cafeteria.
        3. Sleep Shift:
           - Night-owl bots (like Haaland, Neymar, Pradeep) send late-night whispers,
             complaining about hunger or laughing about bugs in #cafeteria / sleep rooms.
        """
        if not guild:
            return

        if self._banter_lock.locked():
            logger.debug("Banter lock already active; skipping autonomous cycle.")
            return

        shift_type = self.get_current_shift_type()

        if shift_type == "work":
            # Target channels: prefer #the-launchpad or #working-chat
            work_candidates = [
                c for c in getattr(guild, "text_channels", [])
                if c.name.lower() in ("working-chat", "the-launchpad")
            ]
            if not work_candidates:
                work_candidates = [
                    c for c in getattr(guild, "text_channels", [])
                    if any(w in c.name.lower() for w in ("working-chat", "the-launchpad", "team-chat", "work", "dev"))
                ]
            target_ch = random.choice(work_candidates) if work_candidates else None

            # Determine squad members based on channel context
            ch_name = target_ch.name.lower() if target_ch else ""
            cat_name = getattr(getattr(target_ch, "category", None), "name", "").lower() if target_ch else ""

            if "launchpad" in ch_name or "vaasan" in cat_name or "vasan" in ch_name:
                squad_members = ["ttf_vasan", "pradeep", "mamitha", "kayadu", "muthazhagi"]
            elif "vijay" in cat_name or "vijay" in ch_name:
                squad_members = ["vijay", "sivakarthikeyan", "anirudh", "trisha", "lokesh"]
            elif "messi" in cat_name or "messi" in ch_name:
                squad_members = ["haaland", "neymar", "messi", "ronaldo", "mbappe"]
            elif "dhoni" in cat_name or "dhoni" in ch_name:
                squad_members = ["virat", "rohit", "dhoni", "hardik", "bumrah"]
            elif "elon" in cat_name or "elon" in ch_name:
                squad_members = ["elon", "altman", "karpathy", "zuck", "lex"]
            elif "stark" in cat_name or "stark" in ch_name:
                squad_members = ["stark", "jarvis", "friday", "rhodey", "vision"]
            else:
                squad_members = random.choice([
                    ["ttf_vasan", "pradeep", "mamitha", "kayadu", "muthazhagi"],
                    ["vijay", "sivakarthikeyan", "anirudh", "trisha", "lokesh"],
                    ["haaland", "neymar", "messi", "ronaldo", "mbappe"],
                    ["virat", "rohit", "dhoni", "hardik", "bumrah"],
                    ["elon", "altman", "karpathy", "zuck", "lex"],
                    ["stark", "jarvis", "friday", "rhodey", "vision"],
                ])

            participants = random.sample(squad_members, k=2)
            scenario = random.choice([
                "pr_merge_conflict_battle",
                "api_payload_mismatch",
                "docker_oom_staging_blocker",
                "sprint_deadline_crunch",
            ])
            await self.run_autonomous_zone_chatter(
                guild=guild,
                zone=ZONE_WORK_SQUAD,
                custom_scenario=scenario,
                participants=participants,
                target_channel=target_ch,
            )

        elif shift_type == "break":
            # Break Shift: spontaneously roast each other, discuss tea/samosa, and banter in #cafeteria
            target_ch = find_cafeteria_channel(guild)
            if not target_ch and hasattr(guild, "text_channels"):
                target_ch = discord.utils.find(
                    lambda c: any(w in c.name.lower() for w in ("cafeteria", "pantry", "lounge", "cafe", "hangout")),
                    guild.text_channels,
                )

            cross_squad_pool = [
                "ttf_vasan", "vijay", "sivakarthikeyan", "pradeep", "anirudh",
                "mamitha", "virat", "rohit", "haaland", "neymar", "kayadu", "trisha",
                "elon", "altman", "karpathy", "stark", "jarvis"
            ]
            participants = random.sample(cross_squad_pool, k=2)
            scenario = random.choice([
                "cutting_chai_samosa_run",
                "friendly_roast_production_bug",
                "movie_trailer_lcu_debate",
                "cricket_ipl_debate",
                "weekend_plans",
            ])
            await self.run_autonomous_zone_chatter(
                guild=guild,
                zone=ZONE_TECH_CAFE,
                custom_scenario=scenario,
                participants=participants,
                target_channel=target_ch,
            )

        else:
            # Sleep Shift: Night-owl bots (like Haaland, Neymar, Pradeep) send late-night whispers,
            # complaining about hunger or laughing about bugs in #cafeteria / sleep rooms
            target_ch = find_cafeteria_channel(guild)
            if not target_ch and hasattr(guild, "text_channels"):
                target_ch = discord.utils.find(
                    lambda c: any(w in c.name.lower() for w in ("cafeteria", "pantry", "dorm", "night", "sleep", "lounge")),
                    guild.text_channels,
                )

            core_night_owls = ["haaland", "neymar", "pradeep"]
            all_night_owls = ["haaland", "neymar", "pradeep", "sivakarthikeyan", "ttf_vasan", "rohit", "anirudh"]
            bot1 = random.choice(core_night_owls)
            bot2 = random.choice([b for b in all_night_owls if b != bot1])
            participants = [bot1, bot2]

            scenario = random.choice([
                "midnight_hunger_pantry_raid",
                "whisper_muthazhagi_rounds",
                "pre_demo_anxiety",
                "bedtime_doomscrolling",
                "night_owl_whispers",
            ])
            await self.run_autonomous_zone_chatter(
                guild=guild,
                zone=ZONE_NIGHT_SPEND,
                custom_scenario=scenario,
                participants=participants,
                target_channel=target_ch,
            )


    def _record_message(self, channel_id: int, sender: str, text: str):
        if channel_id not in self._chat_history:
            self._chat_history[channel_id] = []
        self._chat_history[channel_id].append({"sender": sender, "text": text})
        if len(self._chat_history[channel_id]) > 14:
            self._chat_history[channel_id] = self._chat_history[channel_id][-14:]

    def get_recent_context(self, channel_id: int) -> List[dict]:
        return self._chat_history.get(channel_id, [])[-4:]

    async def get_or_create_webhook(self, channel: discord.TextChannel) -> Optional[discord.Webhook]:
        """
        Retrieves or provisions a webhook in the specified text channel so that
        guest community players (Vijay, Sivakarthikeyan, Anirudh, Trisha, Lokesh)
        can post with their personalized avatar and name.
        """
        if channel.id in self._webhook_cache:
            wh = self._webhook_cache[channel.id]
            if getattr(wh, "channel_id", None) == channel.id:
                return wh

        try:
            webhooks = await channel.webhooks()
            for wh in webhooks:
                if wh.name in ("VaelkryPlayerRelay", "VaelkryCafeteria", "VaelkryRelay"):
                    self._webhook_cache[channel.id] = wh
                    return wh

            wh = await channel.create_webhook(name="VaelkryPlayerRelay")
            self._webhook_cache[channel.id] = wh
            return wh
        except (discord.Forbidden, discord.HTTPException, Exception) as exc:
            logger.debug(f"Webhook unavailable in channel {channel.name}: {exc}")
            return None

    async def send_character_chat(
        self,
        channel: discord.abc.Messageable,
        character_key: str,
        text: str,
        reply_to: Optional[discord.Message] = None,
    ) -> Optional[discord.Message]:
        """
        Dispatches a casual chat message:
        - If character_key corresponds to an active bot client (Team Vasan, Sadie, Millie),
          that bot's native Discord client sends the message directly, supporting native Discord replies.
        - If character_key is a VIP guest (Vijay, SK, Anirudh, Trisha, Lokesh),
          it routes through a channel Webhook with full avatar/name identity.
        - Returns the sent discord.Message or discord.WebhookMessage for conversation chaining.
        """
        char_key = character_key.lower().strip()
        char_info = CASUAL_PLAYER_CHARACTERS.get(char_key, CASUAL_PLAYER_CHARACTERS["vijay"])

        # Track message in AntiRepetitionEngine to update vocabulary history and length modes
        self.anti_repetition_engine.record_message(char_key, text)

        # Human-like typing delay proportional to message length (2.0 to 4.0 seconds)
        char_count = len(text)
        calc_delay = 2.0 + min(1.8, (char_count / 100.0) * 1.5)
        realistic_delay = min(4.0, max(2.0, calc_delay + random.uniform(-0.2, 0.2)))

        if hasattr(channel, "typing"):
            try:
                async with channel.typing():
                    await asyncio.sleep(realistic_delay)
            except Exception:
                await asyncio.sleep(realistic_delay)
        else:
            await asyncio.sleep(realistic_delay)

        sent_msg: Optional[discord.Message] = None

        # Check if character has an active discord.Client session
        if char_key in self.orchestrator.clients:
            client = self.orchestrator.clients[char_key]
            target_ch = client.get_channel(channel.id) if hasattr(channel, "id") else channel
            if target_ch:
                if reply_to:
                    try:
                        sent_msg = await target_ch.send(text, reference=reply_to, mention_author=True)
                    except Exception as exc:
                        logger.debug(f"Native reply reference failed ({exc}), falling back to direct send.")
                        sent_msg = await target_ch.send(text)
                else:
                    sent_msg = await target_ch.send(text)

                if hasattr(channel, "id"):
                    self._record_message(channel.id, char_info["name"], text)
                return sent_msg

        # Guest VIP Player: Attempt webhook delivery
        if isinstance(channel, discord.TextChannel):
            wh = await self.get_or_create_webhook(channel)
            if wh:
                try:
                    sent_msg = await wh.send(
                        content=text,
                        username=char_info["name"],
                        avatar_url=char_info.get("avatar"),
                        wait=True,
                    )
                    if hasattr(channel, "id"):
                        self._record_message(channel.id, char_info["name"], text)
                    return sent_msg
                except Exception as exc:
                    logger.debug(f"Webhook dispatch failed: {exc}, using fallback client.")

        # Fallback: Send through TTF Vasan or available client with clean character badge
        fallback_client = self.orchestrator.clients.get("ttf_vasan") or next(
            iter(self.orchestrator.clients.values()), None
        )
        if fallback_client:
            target_ch = (
                fallback_client.get_channel(channel.id)
                if hasattr(channel, "id")
                else channel
            )
            if target_ch:
                content = f"**[{char_info['title']}]**: {text}"
                if reply_to:
                    try:
                        sent_msg = await target_ch.send(content, reference=reply_to, mention_author=True)
                    except Exception:
                        sent_msg = await target_ch.send(content)
                else:
                    sent_msg = await target_ch.send(content)

                if hasattr(channel, "id"):
                    self._record_message(channel.id, char_info["name"], text)
                return sent_msg

        return None

    async def trigger_bot_comeback(
        self,
        channel: discord.abc.Messageable,
        previous_char_key: str,
        previous_text: str,
    ):
        """
        Spawns an instant, natural, witty comeback or playful counter from a rival
        or teammate bot in common channels (#team-chat, #working-chat, #lounge).
        """
        char_info = CASUAL_PLAYER_CHARACTERS.get(previous_char_key, {})
        rivals = char_info.get("rival_keys", [])
        if not rivals:
            rivals = TEAM_VIJAY_KEYS if char_info.get("team") == "team_vasan" else TEAM_VASAN_KEYS

        comeback_key = random.choice(rivals)
        comeback_info = CASUAL_PLAYER_CHARACTERS.get(comeback_key, CASUAL_PLAYER_CHARACTERS["sivakarthikeyan"])
        ch_name = getattr(channel, "name", "channel")

        guidance = self.anti_repetition_engine.get_dynamic_guidance(comeback_key)
        prompt = build_casual_player_prompt(
            character_key=comeback_key,
            message=previous_text,
            is_bot_reply=True,
            reply_to_bot=char_info.get("name", previous_char_key),
            channel_name=ch_name,
            anti_rep_guidance=guidance,
        )

        try:
            await asyncio.sleep(random.uniform(1.2, 2.2))
            reply = await self.orchestrator.gemini_service.generate_casual_chat(
                prompt=prompt,
                character_name=comeback_info["name"],
            )
            await self.send_character_chat(channel, comeback_key, reply)
        except Exception as exc:
            logger.debug(f"Comeback error for {comeback_key}: {exc}")

    async def chat(
        self,
        character_key: str,
        message: str,
        sender_name: str,
        channel: discord.abc.Messageable,
        allow_comeback: bool = True,
    ) -> str:
        """
        Generates and delivers a single, authentic, casual Discord player reaction,
        with optional spontaneous bot comeback in common channels.
        """
        char_key = character_key.lower().strip()
        char_info = CASUAL_PLAYER_CHARACTERS.get(char_key, CASUAL_PLAYER_CHARACTERS["vijay"])

        ch_id = getattr(channel, "id", 0)
        ch_name = getattr(channel, "name", "channel")
        recent_ctx = self.get_recent_context(ch_id)
        self._record_message(ch_id, sender_name, message)

        guidance = self.anti_repetition_engine.get_dynamic_guidance(char_key)
        prompt = build_casual_player_prompt(
            character_key=char_key,
            message=message,
            sender_name=sender_name,
            recent_context=recent_ctx,
            is_roast=False,
            channel_name=ch_name,
            anti_rep_guidance=guidance,
        )

        try:
            reply = await self.orchestrator.gemini_service.generate_casual_chat(
                prompt=prompt,
                character_name=char_info["name"],
            )
            await self.send_character_chat(channel, char_key, reply)

            # Trigger spontaneous comeback in common channels 50% of the time
            if allow_comeback and is_common_channel(channel) and random.random() < 0.55:
                asyncio.create_task(
                    self.trigger_bot_comeback(
                        channel=channel,
                        previous_char_key=char_key,
                        previous_text=reply,
                    )
                )
            return reply
        except Exception as exc:
            logger.exception(f"Error in casual chat for {char_key}: {exc}")
            fallback_options = char_info.get("fallback_samples") or [char_info.get("sample", "seri vidu")]
            fallback = self.anti_repetition_engine.filter_and_pick_fallback(fallback_options, char_key)
            await self.send_character_chat(channel, char_key, fallback)
            return fallback

    async def roast(
        self,
        character_key: str,
        target: str,
        topic: str,
        sender_name: str,
        channel: discord.abc.Messageable,
        allow_comeback: bool = True,
    ) -> str:
        """
        Delivers a savage, witty Tanglish roast or counter from the specified character,
        with spontaneous teammate laughter or rival comeback.
        """
        char_key = character_key.lower().strip()
        char_info = CASUAL_PLAYER_CHARACTERS.get(char_key, CASUAL_PLAYER_CHARACTERS["sivakarthikeyan"])

        ch_id = getattr(channel, "id", 0)
        ch_name = getattr(channel, "name", "channel")
        recent_ctx = self.get_recent_context(ch_id)

        guidance = self.anti_repetition_engine.get_dynamic_guidance(char_key)
        prompt = build_casual_player_prompt(
            character_key=char_key,
            message=topic or "overall coding logic and scene podradhu",
            sender_name=sender_name,
            recent_context=recent_ctx,
            is_roast=True,
            roast_target=target,
            channel_name=ch_name,
            anti_rep_guidance=guidance,
        )

        try:
            roast_line = await self.orchestrator.gemini_service.generate_casual_chat(
                prompt=prompt,
                character_name=char_info["name"],
            )
            await self.send_character_chat(channel, char_key, roast_line)

            # Trigger a witty comeback or laughing reaction from a teammate or rival
            if allow_comeback and is_common_channel(channel):
                asyncio.create_task(
                    self.trigger_bot_comeback(
                        channel=channel,
                        previous_char_key=char_key,
                        previous_text=f"roast against {target}: {roast_line}",
                    )
                )
            return roast_line
        except Exception as exc:
            logger.exception(f"Error in roast for {char_key}: {exc}")
            fallback_options = [
                f"un alapparai ku alave illama pochu {target} 😂",
                f"idhellam over flex {target}, scene podaama veliya po 💅",
                f"nalla comedy panra pa {target}, mudila bro 😂",
                f"seruppadi counter varum {target}, over-ah valiyudhu thodachuko 💀",
                f"single nu sollitu DM la pesradha paathom {target} 😂",
                f"ketaaya {target}? comedy pannadha vidu.",
            ]
            fallback = self.anti_repetition_engine.filter_and_pick_fallback(fallback_options, char_key)
            await self.send_character_chat(channel, char_key, fallback)
            return fallback

    async def banter(
        self,
        topic: str,
        channel: discord.abc.Messageable,
    ):
        """
        Executes a rapid-fire 4-line mini roast battle / banter among community players.
        """
        if self._banter_lock.locked():
            await channel.send("🔥 **Hold on macha!** Oru banter already chat-la fire aagittu iruku!")
            return

        async with self._banter_lock:
            guidance = self.anti_repetition_engine.get_dynamic_guidance()
            prompt = build_banter_exchange_prompt(topic=topic, anti_rep_guidance=guidance)
            try:
                raw_text = await self.orchestrator.gemini_service.generate_response(
                    prompt=prompt,
                    agent_name="CommunityBanter",
                )

                parsed_turns: List[tuple[str, str]] = []
                for line in raw_text.splitlines():
                    match = re.match(r"^\[([a-zA-Z0-9_]+)\]:\s*(.+)$", line.strip())
                    if match:
                        k = match.group(1).lower().strip()
                        msg = match.group(2).strip()
                        if k in CASUAL_PLAYER_CHARACTERS:
                            parsed_turns.append((k, msg))

                if not parsed_turns:
                    parsed_turns = [
                        ("sivakarthikeyan", f"un alapparai ku alave illama pochu da, {topic} pathi comedy panriya 😂"),
                        ("ttf_vasan", "bayangara scene nanba! 299 speed-la solve panrom!"),
                        ("pradeep", "thalaiva logic illama release panna internal marks poidum maari prod crash aagidum 💀"),
                        ("trisha", "idhellam over flex, whatever u say 💅"),
                        ("lokesh", "pesunathu podhum, deploy pannitu pesunga."),
                    ]

                for char_key, msg in parsed_turns[:5]:
                    await asyncio.sleep(random.uniform(1.2, 2.0))
                    await self.send_character_chat(channel, char_key, msg)

            except Exception as exc:
                logger.exception(f"Error running banter exchange: {exc}")
                await channel.send("💀 Banter server konjam lag aachu nanba, paathukalam vidu!")

    async def clash(
        self,
        topic: str,
        channel: discord.abc.Messageable,
    ):
        """
        Executes a full-scale Team Vasan vs Team Vijay witty roast battle.
        """
        if self._banter_lock.locked():
            await channel.send("⚔️ **Wait panni paaru machan!** Oru squad clash already live-la iruku! 🔥")
            return

        async with self._banter_lock:
            guidance = self.anti_repetition_engine.get_dynamic_guidance()
            prompt = build_cross_team_clash_prompt(topic=topic, anti_rep_guidance=guidance)
            try:
                raw_text = await self.orchestrator.gemini_service.generate_response(
                    prompt=prompt,
                    agent_name="SquadClash",
                )
                parsed_turns: List[tuple[str, str]] = []
                for line in raw_text.splitlines():
                    match = re.match(r"^\[([a-zA-Z0-9_]+)\]:\s*(.+)$", line.strip())
                    if match:
                        k = match.group(1).lower().strip()
                        msg = match.group(2).strip()
                        if k in CASUAL_PLAYER_CHARACTERS:
                            parsed_turns.append((k, msg))

                if not parsed_turns:
                    parsed_turns = [
                        ("ttf_vasan", f"bayangara scene nanba! 299 speed-la {topic} solve panrom, Team Vasan mass da!"),
                        ("sivakarthikeyan", "un alapparai ku alave illama pochu da, throttle twist panna server ke kannu verkum 😂"),
                        ("pradeep", "thalaiva wait panni paaru, logic puriyama comedy pannatha bro 💀"),
                        ("vijay", "all is well machan, timing super aana deploy mudinjutha illa thirumba bug ah? 🦁"),
                        ("anirudh", "vibe-eh vera level beats drop aagudhu, marathon code sprint mode on! 🎵"),
                        ("trisha", "idhellam over flex boys, scene podaama veliya ponga 💅"),
                        ("lokesh", "pesunathu podhum da, deploy pannitu pesunga."),
                    ]

                for char_key, msg in parsed_turns[:7]:
                    await asyncio.sleep(random.uniform(1.3, 2.2))
                    await self.send_character_chat(channel, char_key, msg)

            except Exception as exc:
                logger.exception(f"Error during squad clash: {exc}")
                await channel.send("💀 Squad clash lag aachu nanba, paathukalam vidu!")

    async def handle_mention_reply(
        self,
        listener_client: Any,
        message: discord.Message,
    ):
        """
        Triggers natural Discord player replies when any of the 7 active bots
        is explicitly @mentioned or replied to by a human user.
        """
        if message.author.bot or message.author.id in self.orchestrator.bot_user_ids:
            return

        bot_key = listener_client.agent_config.key
        if bot_key not in CASUAL_PLAYER_CHARACTERS:
            return

        clean_text = message.content
        for mention in message.mentions:
            clean_text = clean_text.replace(f"<@{mention.id}>", "").replace(f"<@!{mention.id}>", "")
        clean_text = clean_text.strip()
        if not clean_text:
            clean_text = "wassup"

        try:
            async with message.channel.typing():
                await asyncio.sleep(random.uniform(1.0, 2.0))
                await self.chat(
                    character_key=bot_key,
                    message=clean_text,
                    sender_name=message.author.display_name,
                    channel=message.channel,
                    allow_comeback=True,
                )
        except Exception as exc:
            logger.debug(f"Error handling mention reply for {bot_key}: {exc}")

    async def handle_contextual_reaction(self, message: discord.Message):
        """
        Contextual, non-spam reaction emojis:
        Bots selectively react (with 20-30% organic chance) using relatable emojis
        (😂, 🔥, 💀, ☕, 🏍️, 😎) based on chat keywords.
        """
        # Exclude self-reactions to bot messages from our orchestrator
        if message.author.bot and message.author.id in self.orchestrator.bot_user_ids:
            return

        # Selective organic chance (20% - 30%)
        if random.random() > 0.28:
            return

        text = message.content.lower().strip()
        if not text:
            return

        # Keyword mapping to contextual emojis
        keyword_emoji_map = [
            (
                ["haha", "lol", "lmao", "roast", "comedy", "joke", "kannu verkum", "scene", "mudila", "fun", "siripu", "vadivelu"],
                "😂",
            ),
            (
                ["fire", "mass", "deploy", "sprint", "rocket", "speed", "thookuvom", "vera level", "release", "ship", "launch", "fast"],
                "🔥",
            ),
            (
                ["bug", "crash", "error", "exception", "fail", "lag", "dead", "broken", "rip", "issue", "panic"],
                "💀",
            ),
            (
                ["coffee", "chai", "tea", "break", "pantry", "snack", "cafeteria", "biscuit", "samosa", "eat", "drink"],
                "☕",
            ),
            (
                ["vasan", "bike", "299", "throttle", "ride", "vroom", "ktm", "ninja"],
                "🏍️",
            ),
            (
                ["vijay", "thalapathy", "cool", "swag", "thalaiva", "style", "mass", "leo", "goat", "master"],
                "😎",
            ),
        ]

        matched_emojis = []
        for keywords, emoji in keyword_emoji_map:
            if any(k in text for k in keywords):
                matched_emojis.append(emoji)

        if not matched_emojis:
            # Fallback for general developer banter
            if len(text) > 15 and any(w in text for w in ("bro", "macha", "nanba", "thalaiva", "code", "dev")):
                matched_emojis = ["🔥", "😎", "😂", "☕"]
            else:
                return

        chosen_emoji = random.choice(matched_emojis)

        # Pick one active bot client to add the reaction
        active_clients = [c for c in self.orchestrator.clients.values() if c.is_ready()]
        if not active_clients:
            return

        reacting_client = random.choice(active_clients)
        try:
            target_ch = reacting_client.get_channel(message.channel.id) or message.channel
            msg_to_react = await target_ch.fetch_message(message.id) if hasattr(target_ch, "fetch_message") else message
            await msg_to_react.add_reaction(chosen_emoji)
            logger.debug(f"{reacting_client.user.name if reacting_client.user else 'Bot'} reacted {chosen_emoji} to message {message.id}")
        except Exception as exc:
            logger.debug(f"Failed to add contextual reaction {chosen_emoji}: {exc}")

    async def run_autonomous_zone_chatter(
        self,
        guild: discord.Guild,
        zone: Optional[str] = None,
        custom_scenario: Optional[str] = None,
        participants: Optional[List[str]] = None,
        target_channel: Optional[discord.TextChannel] = None,
    ):
        """
        Hyper-Realistic Autonomous 3-Zone Conversation Engine:
        Executes dynamic, contextual multi-bot conversations across:
        1. Zone 1: Work Squad Rooms (During Work Shifts)
           - Focus: PR merge conflicts, git rebase, API payload mismatches (userId vs user_id),
             Docker OOMKilled staging blockers, Figma vs CSS padding, sprint crunch.
           - Tone: Professional, slightly stressed, collaborative engineering peers in Tanglish.
           - Target: Squad text channels (#working-chat, #the-launchpad).
        2. Zone 2: Tech Cafe & Pantry (During Breaks / Relax Shifts)
           - Focus: Cutting chai / samosa runs, movie trailers / LCU theories, cricket debates,
             friendly roasts about silly bugs (console.log in prod), weekend plans.
           - Tone: Fun, energetic, informal collegial banter.
           - Target: #cafeteria.
        3. Zone 3: Night Spend / Dorms (During Sleep Shifts)
           - Focus: Midnight hunger / pantry fridge raids, whispering to avoid waking others,
             fear of Muthazhagi HR/QA night inspection rounds, pre-demo anxiety for 10 AM CEO demo,
             bedtime scrolling reels.
           - Dynamic: 2 night owls (Haaland, Neymar, Pradeep, Sivakarthikeyan, TTF Vasan) in soft whispers.
           - Target: #cafeteria (sneaking into pantry) or dorm text channels.

        Mentions & Chaining:
        - Resolves live member tags (<@{id}>) for natural in-text mentions.
        - Employs native Discord replies (reply_to=prev_msg) with 2-4s typing delay.
        """
        if self._banter_lock.locked():
            logger.debug("Banter lock active; skipping zone chatter cycle.")
            return

        # 1. Resolve Zone dynamically if not specified
        if not zone:
            current_shift_id = getattr(self.orchestrator.scheduler_service, "current_shift_id", "work_squad")
            if current_shift_id == "sleep":
                zone = ZONE_NIGHT_SPEND
            elif current_shift_id in ("warmup", "rest_1", "rest_2", "rest_3", "rest_4"):
                zone = ZONE_TECH_CAFE
            else:
                zone = ZONE_WORK_SQUAD

        zone = zone.lower().strip()
        if zone not in ZONE_METADATA:
            zone = ZONE_WORK_SQUAD

        # 2. Resolve Target Channel according to Zone
        target_ch = target_channel
        if not target_ch:
            if zone == ZONE_WORK_SQUAD:
                # Prefer work squad text channels (#working-chat, #the-launchpad)
                work_candidates = [
                    c for c in getattr(guild, "text_channels", [])
                    if c.name.lower() in ("working-chat", "the-launchpad")
                    or any(w in c.name.lower() for w in ("working-chat", "the-launchpad", "team-chat", "work", "dev"))
                ]
                if work_candidates:
                    target_ch = random.choice(work_candidates)
            elif zone == ZONE_TECH_CAFE:
                target_ch = find_cafeteria_channel(guild)
                if not target_ch and hasattr(guild, "text_channels"):
                    target_ch = discord.utils.find(
                        lambda c: any(w in c.name.lower() for w in ("cafeteria", "pantry", "lounge", "cafe", "hangout")),
                        guild.text_channels,
                    )
            elif zone == ZONE_NIGHT_SPEND:
                # Night owls sneak into cafeteria pantry or whisper in team chat
                target_ch = find_cafeteria_channel(guild)
                if not target_ch and hasattr(guild, "text_channels"):
                    target_ch = discord.utils.find(
                        lambda c: any(w in c.name.lower() for w in ("cafeteria", "pantry", "dorm", "night", "sleep", "lounge")),
                        guild.text_channels,
                    )

        # Fallback channel if specific zone channel not found
        if not target_ch and hasattr(guild, "text_channels") and guild.text_channels:
            fallback_chs = [c for c in guild.text_channels if "announcement" not in c.name.lower()]
            target_ch = fallback_chs[0] if fallback_chs else guild.text_channels[0]

        if not target_ch:
            logger.warning(f"Could not find any suitable channel for zone chatter ({zone}).")
            return

        # 3. Select Participants based on Zone
        characters: List[str] = []
        if participants:
            characters = list(participants)
        elif zone == ZONE_WORK_SQUAD:
            category_name = getattr(target_ch.category, "name", "").lower() if getattr(target_ch, "category", None) else ""
            ch_name = target_ch.name.lower()
            if "vijay" in category_name or "vijay" in ch_name:
                squad_members = ["vijay", "sivakarthikeyan", "anirudh", "trisha", "lokesh"]
            elif "vaasan" in category_name or "vasan" in ch_name or "launchpad" in ch_name:
                squad_members = ["ttf_vasan", "pradeep", "mamitha", "kayadu", "muthazhagi"]
            elif "messi" in category_name or "messi" in ch_name:
                squad_members = ["messi", "ronaldo", "haaland", "neymar", "mbappe"]
            elif "dhoni" in category_name or "dhoni" in ch_name:
                squad_members = ["dhoni", "virat", "rohit", "hardik", "bumrah"]
            elif "elon" in category_name or "elon" in ch_name:
                squad_members = ["elon", "altman", "karpathy", "zuck", "lex"]
            elif "stark" in category_name or "stark" in ch_name:
                squad_members = ["stark", "jarvis", "friday", "rhodey", "vision"]
            else:
                squad_members = random.choice([
                    ["ttf_vasan", "pradeep", "mamitha", "kayadu", "muthazhagi"],
                    ["vijay", "sivakarthikeyan", "anirudh", "trisha", "lokesh"],
                    ["haaland", "neymar", "messi", "ronaldo", "mbappe"],
                    ["virat", "rohit", "dhoni", "hardik", "bumrah"],
                    ["elon", "altman", "karpathy", "zuck", "lex"],
                    ["stark", "jarvis", "friday", "rhodey", "vision"],
                ])
            # 2 squad engineers
            characters = random.sample(squad_members, k=2)

        elif zone == ZONE_TECH_CAFE:
            # Cross-squad colleagues meeting at cafeteria
            cross_squad_pool = [
                "ttf_vasan", "vijay", "sivakarthikeyan", "pradeep", "anirudh",
                "mamitha", "virat", "rohit", "haaland", "neymar", "kayadu",
                "elon", "altman", "karpathy", "stark", "jarvis"
            ]
            characters = random.sample(cross_squad_pool, k=2)

        elif zone == ZONE_NIGHT_SPEND:
            # 2 night owls sneaking late at night (Haaland, Neymar, Pradeep, SK, TTF Vasan, Rohit)
            core_night_owls = ["haaland", "neymar", "pradeep"]
            all_night_owls = ["haaland", "neymar", "pradeep", "sivakarthikeyan", "ttf_vasan", "rohit", "anirudh"]
            bot1 = random.choice(core_night_owls)
            bot2 = random.choice([b for b in all_night_owls if b != bot1])
            characters = [bot1, bot2]

        # 4. Resolve Scenario
        zone_presets = ZONE_PRESETS.get(zone, {})
        valid_scenarios = list(zone_presets.keys())
        scenario = custom_scenario if (custom_scenario and custom_scenario in valid_scenarios) else (
            random.choice(valid_scenarios) if valid_scenarios else "default_scenario"
        )

        # 5. Build Character Discord Mention Map for Natural Tags
        character_tag_map: Dict[str, str] = {}
        for k in characters:
            char_data = CASUAL_PLAYER_CHARACTERS.get(k, {})
            # Check bot client user ID
            if k in self.orchestrator.clients:
                cl = self.orchestrator.clients[k]
                if cl.user:
                    character_tag_map[k] = f"<@{cl.user.id}>"
                    continue
            # Search guild members by name / display name
            matched_m = discord.utils.find(
                lambda m: char_data.get("name", "").lower() in m.name.lower() or char_data.get("title", "").lower() in m.display_name.lower(),
                getattr(guild, "members", []),
            )
            if matched_m:
                character_tag_map[k] = f"<@{matched_m.id}>"
            else:
                character_tag_map[k] = f"@{char_data.get('name', k)}"

        async with self._banter_lock:
            parsed_turns: List[tuple[str, str]] = []
            guidance = self.anti_repetition_engine.get_dynamic_guidance()
            prompt = build_zone_conversation_prompt(
                zone=zone,
                characters=characters,
                scenario_type=scenario,
                anti_rep_guidance=guidance,
                character_tag_map=character_tag_map,
            )

            try:
                raw_text = await self.orchestrator.gemini_service.generate_response(
                    prompt=prompt,
                    agent_name=f"ZoneChatter_{zone}",
                )
                for line in raw_text.splitlines():
                    match = re.match(r"^\[([a-zA-Z0-9_]+)\]:\s*(.+)$", line.strip())
                    if match:
                        k = match.group(1).lower().strip()
                        msg = match.group(2).strip()
                        if k in CASUAL_PLAYER_CHARACTERS:
                            parsed_turns.append((k, msg))
            except Exception as exc:
                logger.warning(f"Error generating AI conversation for {zone} ({scenario}): {exc}")

            # Enforce crisp 3 to 5 multi-turn exchanges with curated presets fallback
            if len(parsed_turns) < 3:
                preset_options = zone_presets.get(scenario, [])
                if preset_options:
                    raw_preset = random.choice(preset_options)
                    # Replace {tag_a} and {tag_b} with resolved mentions
                    char_a = characters[0] if len(characters) > 0 else "ttf_vasan"
                    char_b = characters[1] if len(characters) > 1 else "pradeep"
                    tag_a = character_tag_map.get(char_a, f"@{char_a}")
                    tag_b = character_tag_map.get(char_b, f"@{char_b}")
                    preset_speakers = []
                    for spk, _ in raw_preset:
                        if spk not in preset_speakers:
                            preset_speakers.append(spk)

                    parsed_turns = []
                    for spk, text_line in raw_preset[:5]:
                        mapped_spk = spk
                        if len(characters) == 2 and spk not in characters:
                            if len(preset_speakers) >= 2:
                                mapped_spk = char_a if spk == preset_speakers[0] else char_b
                            else:
                                mapped_spk = char_a
                        fmt_line = text_line.replace("{tag_a}", tag_a).replace("{tag_b}", tag_b)
                        parsed_turns.append((mapped_spk, fmt_line))
            elif len(parsed_turns) > 5:
                parsed_turns = parsed_turns[:5]

            if not parsed_turns:
                logger.warning(f"No parsed turns available for zone conversation ({zone}, {scenario}).")
                return

            # Zone-specific natural closing check
            last_speaker, last_text = parsed_turns[-1]
            if zone == ZONE_NIGHT_SPEND:
                has_closing = any(
                    w in last_text.lower()
                    for w in ("sleep", "thoong", "padu", "bed", "curfew", "muthu", "muthazhagi", "log", "escape", "room", "lights out", "shhh", "discipline")
                )
                if not has_closing:
                    closing_speaker = random.choice([c for c in characters if c != last_speaker] or characters)
                    closing_lines = [
                        "shhh muthazhagi akka dorm door sound kekudhu, silent-ah sleep room-ku escape aagidalam 🏃‍♂️💨",
                        "podhum da 3 AM aachu, alarm vaikala na sethom, thoonga polam 😴",
                        "seri lights off, dark circles confirm aagidum, sleep room-ku odunga 💤",
                        "ketaaya? muthazhagi akka round-up vara maari iruku, sleep room poiduvom 🤫",
                        "kannu eriudhu, bed-la saanjaachu, quiet-ah sleep room polam 🌙",
                    ]
                    closing_pick = self.anti_repetition_engine.filter_and_pick_fallback(closing_lines, closing_speaker)
                    if len(parsed_turns) < 5:
                        parsed_turns.append((closing_speaker, closing_pick))
                    else:
                        parsed_turns[-1] = (closing_speaker, closing_pick)

            elif zone == ZONE_WORK_SQUAD:
                has_closing = any(
                    w in last_text.lower()
                    for w in ("pr", "merge", "rebase", "deploy", "build", "push", "test", "done", "seri", "check")
                )
                if not has_closing:
                    closing_speaker = random.choice([c for c in characters if c != last_speaker] or characters)
                    closing_lines = [
                        "seri, rebase clean aagudhu, PR-ku LGTM podunga fast-ah 🚀",
                        "staging podren, logs check pannitu சொல்லுங்க 👍",
                        "conflict resolved da, push panren ipove 💻",
                    ]
                    closing_pick = self.anti_repetition_engine.filter_and_pick_fallback(closing_lines, closing_speaker)
                    if len(parsed_turns) < 5:
                        parsed_turns.append((closing_speaker, closing_pick))
                    else:
                        parsed_turns[-1] = (closing_speaker, closing_pick)

            logger.info(
                f"Delivering Zone [{zone}] conversation in #{target_ch.name} "
                f"({scenario}, {len(parsed_turns)} turns across: {characters})"
            )

            # Deliver messages sequentially using native Discord reply chaining
            prev_msg: Optional[discord.Message] = None
            for idx, (char_key, msg) in enumerate(parsed_turns):
                # Chain native reply to the immediately preceding message
                sent_msg = await self.send_character_chat(target_ch, char_key, msg, reply_to=prev_msg)
                if sent_msg:
                    prev_msg = sent_msg

                # Dynamic delay between turns: zone 3 (sleep) has softer pauses (2.5-4.0s), others (2.0-3.2s)
                pause_range = (2.5, 4.0) if zone == ZONE_NIGHT_SPEND else (2.0, 3.2)
                await asyncio.sleep(random.uniform(*pause_range))

    async def run_autonomous_night_chatter(
        self,
        guild: discord.Guild,
        custom_scenario: Optional[str] = None,
    ):
        """
        Backward-compatible alias for Zone 3 (Night Spend) autonomous chatter.
        """
        return await self.run_autonomous_zone_chatter(
            guild=guild,
            zone=ZONE_NIGHT_SPEND,
            custom_scenario=custom_scenario,
        )

    async def handle_cafeteria_user_chat(self, message: discord.Message):
        """
        Manual Trigger Support:
        When a user pings @everyone or types in #cafeteria (like 'hi', 'enna pandringa da'),
        1 to 2 random awake bots reply back naturally within 3 seconds instead of ignoring.
        """
        if message.author.bot or message.author.id in self.orchestrator.bot_user_ids:
            return

        clean_text = message.content.strip()
        for mention in message.mentions:
            clean_text = clean_text.replace(f"<@{mention.id}>", "").replace(f"<@!{mention.id}>", "")
        clean_text = clean_text.replace("@everyone", "").replace("@here", "").strip()

        # Check shift
        current_shift_id = getattr(self.orchestrator.scheduler_service, "current_shift_id", None)
        is_sleep_shift = (current_shift_id == "sleep")

        # Pick 1 to 2 bots
        num_bots = 2 if random.random() < 0.45 else 1
        if is_sleep_shift:
            candidate_keys = ["sivakarthikeyan", "pradeep", "ttf_vasan", "mamitha", "trisha", "virat", "ronaldo", "anirudh", "muthazhagi", "rohit"]
        else:
            candidate_keys = ["ttf_vasan", "sivakarthikeyan", "pradeep", "mamitha", "trisha", "vijay", "anirudh", "virat", "rohit", "messi"]

        chosen_keys = random.sample(candidate_keys, k=num_bots)

        night_fallback_pool: Dict[str, List[str]] = {
            "sivakarthikeyan": [
                "kannu eriudhu bro, alarm vaikala na sethom morning standup-ku 😴",
                "seri, silent-ah irunga, muthazhagi akka kettuta kola gaandu aagiduvaanga 💀",
                "single nu sollitu DM la pesradha paathom, cafeteria la enna scene? 😂",
                "valo lobby la clutch panna maari cafeteria fridge lock open panniten 🎮",
                "seruppadi comedy pannadha bro, tea stall-ku nadakka mudiyadhu, thoonga polam ☕",
                "dark circles confirm aaiduchu, blanket-kulla poiduvom 💤",
                "ketaaya? muthazhagi akka dorm door sound kekudhu, silent! 🤫",
                "canteen samosa kooda kedaikala, midnight hunger trigger vera 🥲",
            ],
            "pradeep": [
                "mudila bro, internal marks poidum maari prod bug tension eluppudhu 💀",
                "idhellam over flex bro, 3 AM ku cafeteria la scene podaama veliya po 😂",
                "thala suthudhu, bed-la saanjaachu, silent mode on 😴",
                "apdiya? 300ms ping la bgmi clutch aada maari cafeteria la tea theduriya ☕",
                "over-ah valiyudhu thodachuko, blanket-kulla scroll pannitu iruken 📱",
                "seri vidu, sem exam tension maari muthazhagi raid bayam iruku 🏃‍♂️💨",
                "dark circles confirm, overthinking script close pannitu paduka poren 💤",
                "ez win nu nenachen, fridge-la dairy milk kooda illa 🍫",
            ],
            "ttf_vasan": [
                "bayangara scene nanba! 299 throttle twist speed la bed-la saanjaachu 🏍️",
                "seri, mid-night hunger trigger aaiduchu, quick snack eduthutu escape! 🤫",
                "kannu eriudhu nanba, tea stall-ku nadakka mudiyadhu, sleep room poiduvom 💤",
                "kola gaandu aagida koodadhu muthazhagi akka, silent mode! ⚠️",
                "valo lobby clutch maari corner hairpin bend la sleep room odidurom 🏍️💨",
                "un alapparai ku alave illama pochu, lights out poiduvom! 😴",
                "podhum, alarm vaikala na sethom, good night! 🌙",
            ],
            "mamitha": [
                "aiyoo dark circles confirm! aesthetic skin care waste aagidum 🌸",
                "un alapparai ku alave illama pochu bro, fridge la dairy milk theda vidunga 🍫✨",
                "blanket-kulla scroll pannitu iruken, silent ah pesunga 😴",
                "kannu eriudhu, sem exam tension maari muthazhagi akka raid bayangara scene 💀",
                "scene podaama veliya po bro, bed-la saanjaachu 🌸💅",
                "apdiya? tea stall-ku nadakka mudiyadhu, cafeteria kettle off pannitu thoongunga ☕",
                "mudila, aesthetic sleep mode on ✨💤",
            ],
            "trisha": [
                "over-ah valiyudhu thodachuko, go to bed already 💅",
                "single nu sollitu DM la pesradha paathom, stop whispering in cafeteria 💀",
                "dark circles confirm for you, bed-la saanjaachu, bye 😴",
                "idhellam over flex bro, silent-ah escape aagidunga 💅",
                "canteen samosa kooda kedaikala maari drama podadheenga, sleep room polam ☕",
                "ketaaya? muthazhagi akka footstep kekudhu, run 💅",
                "seri, lights off.",
            ],
            "muthazhagi": [
                "NILLU! seruppadi vangama sleep room-ku odunga da! Curfew strictly enforced! 🛡️",
                "kola gaandu aakama padunga! Security incident log file panren! ⚠️",
                "assignment submit pannala na professor thitta poraaru maari Yogesh brother kitta complain podren! 🛡️",
                "bayangara scene podra yaaru adhu midnight cafeteria la? Bed-la saanjaachu ponga! 💥",
                "thala suthudhu ungalala, silent mode follow pannalana mute panniduven! 🛑",
                "podhum un alappara! sleep room-ku escape aagu! 🛡️",
            ],
            "ronaldo": [
                "sleep is essential for 100% performance! SIUUU 💤",
                "dark circles confirm if you don't sleep now! Zero warnings discipline! 💪",
                "bgmi clutch maari morning 5 AM workout wait panren! Bed-la saanjaachu 🏋️‍♂️",
                "ez win requires 8 hours sleep! No cafeteria noise! SIUUU ⚡",
                "seri, lights out!",
            ],
            "virat": [
                "aggressive recovery mode on! Kannu eriudhu boys, sleep room polam 🏏",
                "alarm vaikala na sethom morning practice-ku! No midnight wandering! 🔥",
                "clutch or kick situation in cafeteria, muthazhagi akka vara poraanga, sleep room poiduvom 💀",
                "sem exam tension maari intensity venum code-la, ipo thoongunga 🏏💤",
                "podhum, bed-la saanjaachu!",
            ],
            "anirudh": [
                "vibe-eh vera at 3 AM synth loop mind la, aana kannu eriudhu 🎵",
                "mid-night hunger trigger aachu, aana tea stall-ku nadakka mudiyadhu ☕🎧",
                "bakkunu aaiduchu muthazhagi akka door sound kettutu! Sleep room escape 🎹",
                "dark circles confirm, acoustic lullaby beat potu thoonga poren 😴",
                "seri vidu, silent mode.",
            ],
            "rohit": [
                "pantry fridge la vadapav theditu iruken ya, mid-night hunger trigger 🍔",
                "thala suthudhu, ping 300ms aagudhu maari brain slow aachu, bed-la saanjaachu 💤",
                "clutch or kick tension edhuku? Match 20th over mudinjudhu, relax ya 🍔",
                "canteen samosa kooda kedaikala, silent-ah thoonga vidunga ya 😴",
                "seri, lights out ya.",
            ],
            "messi": [
                "calm down boys, O(1) logic thavira midnight-la no scene ⚽",
                "dark circles confirm aagida koodadhu, sleep room polam 🎧",
                "bed-la saanjaachu, quiet coffee sip pannitu padunga ☕💤",
                "seri, good night.",
            ],
            "vijay": [
                "nanba alappara podhum, silent-ah sleep room poiduvom 🦁",
                "kannu eriudhu, morning fresh-ah mission thookuvom, bed-la saanju rest edunga 💤",
                "idhellam over flex, muthazhagi akka log potruvaanga, sleep mode on 🦁",
                "seri, all is well.",
            ],
            "kayadu": [
                "sappa matter, cluster healthy. silent-ah sleep room escape aagidalam.",
                "thala suthudhu nu tension aagadheenga, kettle off pannitu padunga.",
                "bed-la saanju rest edunga, backend safe dhaan.",
                "seri, good night.",
            ],
            "lokesh": [
                "pesunathu podhum, 3 AM ku sleep room poidunga.",
                "action speaks, midnight scene podaama escape.",
                "clutch or kick, muthazhagi raid start aagudhu.",
                "seri, time aachu.",
            ],
        }

        day_fallback_pool: Dict[str, List[str]] = {
            "sivakarthikeyan": [
                "Hi thalaiva! Cafeteria biscuit packet open pannitom, vaa galaatta pannuvom 😂",
                "valo lobby clutch maari tea cup handle panren paaru ☕🎮",
                "single nu sollitu DM la pesradha paathom, cafeteria la enna comedy? 😂",
                "un alapparai ku alave illama pochu, hot chai ready ☕",
                "canteen samosa kooda kedaikala bro, biscuit-oda adjust pannuvom 🍪",
                "seri, vaa pesuvom.",
            ],
            "pradeep": [
                "Wassup bro, coffee kudichute database logic analyze panren ☕",
                "internal marks poidum maari staging bug tension aachu, tea kudikrom 💀",
                "idhellam over flex bro, scene podaama cafeteria coffee enjoy pannu 😂",
                "thala suthudhu logic eludhi, quick break eduthutu PR merge pannanum 🧠",
                "ez win dhaan, next sprint architecture ready 💻",
                "apdiya? vaa join pannu.",
            ],
            "ttf_vasan": [
                "bayangara scene nanba! 299 speed la tea break mudikrom! 🔥🏍️",
                "Nanba cafeteria vibe semma! Hot chai ready, sprint thookuvom! ☕",
                "un alapparai ku alave illama pochu mapla, rocket speed deploy! 🚀",
                "kola gaandu aakama cafeteria tea kudichutu energetic-ah vaanga! 🏍️",
                "valo lobby clutch maari corner bend la cafeteria arrive aayitom 🏍️",
                "seri, vaa nanba!",
            ],
            "mamitha": [
                "Hello hello! Cafeteria aesthetic vibe 10/10, coffee enjoy pannu bro ✨",
                "over-ah valiyudhu thodachuko bro, glassmorphic tea cup ready 🌸☕",
                "un alapparai ku alave illama pochu, clean UI vibes enjoy pannunga ✨",
                "canteen samosa kedaikala nu feel pannadha bro, pastry order panniduvom 🥐",
                "vibe-eh vera level aesthetic in cafeteria today 🌸",
                "seri, welcome!",
            ],
            "trisha": [
                "hey! grab a coffee and chill with us ☕💅",
                "idhellam over flex bro, high fashion break vibes only ✨",
                "single nu sollitu DM la pesradha paathom, cafeteria la cool look 💅",
                "scene podaama veliya po nu solla maaten, take a latte ☕",
                "seri, enjoy your coffee.",
            ],
            "vijay": [
                "Hi nanba, calm-ah break eduthutu adutha mission start pannuvom 🦁",
                "Wassup nanba, tea break peaceful-ah pogudhu, all is well ☕",
                "idhellam over flex machan, cool-ah execute pannuvom 🦁",
                "sappa matter, break mudinju masterclass code release panrom 🦁",
                "seri, enjoy the tea.",
            ],
            "anirudh": [
                "vibe-eh vera! coffee beat drop aagudhu, join the rhythm! 🎵",
                "Wassup machan, tea and music mode on full volume 🎧",
                "bakkunu aaiduchu cafeteria playlist super-ah iruku 🎹",
                "acoustic vibes + hot chai = next blockbuster track 🔥☕",
                "seri, vibe on.",
            ],
            "virat": [
                "Wassup bro! Quick high-energy tea break, back to 100% focus soon! 🏏",
                "Energy level 100%! Clutch or kick intensity for next sprint 🔥",
                "sem exam tension maari aggression code-la venum, take quick fuel 💥",
                "zero sloppy code, 100% precision! Tea kudichutu adippom 🏏",
                "seri, lets go!",
            ],
            "rohit": [
                "Snacks kedaichudha bro? Vadapav or tea eduthutu chill pannu 🍔",
                "Hi ya, relaxed energy always gives best output! Oru vadapav saapdu ☕",
                "canteen samosa kooda kedaikala na vadapav dhaan solution 🍔",
                "tension edhuku ya? match control-la iruku, tea kudipom 🍟",
                "seri ya, chill.",
            ],
            "messi": [
                "Calm coffee break brother, simple clean execution ⚽",
                "Hi brother, O(1) logic thavira break-la pure peace ☕",
                "no flex needed, benchmark results speak ⚽",
                "seri, take coffee.",
            ],
            "kayadu": [
                "cool-ah irunga, cafeteria kettle on panniten. hot tea ready ☕",
                "sappa matter, cluster deployment healthy. peaceful break.",
                "relax, production safe dhaan, tea enjoy pannunga.",
                "seri, all good.",
            ],
            "muthazhagi": [
                "tea kudichutu odane test cases verify pannanum! zero bugs allowed! 🛡️",
                "assignment submit pannala maari break time-la lag aagadha da! ⚠️",
                "kola gaandu aakama quick tea mudichutu PR review-ku vaanga 🛡️",
                "seri, tea kudichutu vela paaru.",
            ],
        }

        user_prompt_text = clean_text if clean_text else "hi everyone enna pandringa da"

        for bot_idx, bot_key in enumerate(chosen_keys):
            if bot_idx > 0:
                await asyncio.sleep(random.uniform(1.8, 3.2))

            reply_text = None
            char_info = CASUAL_PLAYER_CHARACTERS.get(bot_key, {})
            char_name = char_info.get("name", bot_key)

            # Try generating dynamic context-aware response via Gemini
            try:
                shift_context = (
                    "Night Spend (Sleep Shift - everyone is supposed to be sleeping, whispering sneaked out into #cafeteria)"
                    if is_sleep_shift
                    else "Daytime Cafeteria Break"
                )
                guidance = self.anti_repetition_engine.get_dynamic_guidance(bot_key)
                avoids = guidance.get("avoid_words", [])
                avoid_str = f"Strictly avoid reusing these words: {', '.join(avoids)}." if avoids else ""

                prompt = (
                    f"You are {char_name} in Vaelkry Dev Labs Discord.\n"
                    f"Vibe: {char_info.get('vibe', '')}\n"
                    f"Current context: {shift_context}.\n"
                    f"User '{message.author.display_name}' just said in #cafeteria: '{user_prompt_text}'.\n"
                    f"{avoid_str}\n"
                    f"Target length: {guidance.get('length_instruction', '')}\n"
                    f"Atmospheric tone: {guidance.get('tone_flavor', '')}\n"
                    f"Reply naturally in authentic Tanglish. Output ONLY the raw message."
                )
                reply_text = await self.orchestrator.gemini_service.generate_casual_chat(
                    prompt=prompt,
                    character_name=char_name,
                )
            except Exception as exc:
                logger.debug(f"Gemini response failed for {bot_key} cafeteria chat: {exc}")

            if not reply_text:
                pool = night_fallback_pool if is_sleep_shift else day_fallback_pool
                bot_lines = pool.get(bot_key, [f"hi {message.author.display_name}, cafeteria la chill panrom!"])
                reply_text = self.anti_repetition_engine.filter_and_pick_fallback(bot_lines, bot_key)

            await self.send_character_chat(message.channel, bot_key, reply_text)

    def find_squad_working_channel(self, guild: discord.Guild, squad_key: str) -> Optional[discord.TextChannel]:
        """Locates the designated working-chat channel for a given squad."""
        return find_squad_working_channel(guild, squad_key)

    async def dispatch_executive_directive(
        self,
        guild: discord.Guild,
        squad_key: Optional[str] = None,
    ) -> bool:
        """
        Sadie & Millie Executive Task Dispatch Engine:
        Autonomously dispatches concrete, high-value technical and commercial directives
        to a designated squad's #working-chat channel.

        Sequential 4-turn interaction flow:
        1. Sadie Sink (CEO) posts executive business strategy, pricing, monetization targets, and sprint priorities.
        2. Millie Bobby Brown (COO) replies to Sadie with granular technical specs, PR deadlines, architectural patterns, and testing expectations.
        3. Squad Lead (TTF Vasan, Vijay, Messi, Dhoni, Elon, Stark) acknowledges and delegates to squad members.
        4. Senior Squad Dev replies with PR estimation, architecture status, and delivery ETA.
        """
        all_squads = ["team_vasan", "team_vijay", "team_messi", "team_dhoni", "team_elon", "team_stark"]
        chosen_squad = squad_key.lower().strip() if squad_key else random.choice(all_squads)
        if chosen_squad not in EXECUTIVE_DIRECTIVES_CATALOG:
            chosen_squad = "team_vasan"

        target_ch = self.find_squad_working_channel(guild, chosen_squad)
        if not target_ch:
            logger.warning(f"Could not locate working channel for squad '{chosen_squad}'.")
            return False

        directive_data = random.choice(EXECUTIVE_DIRECTIVES_CATALOG[chosen_squad])
        lead_key = directive_data["lead_key"]
        dev_key = directive_data["dev_key"]
        project_title = directive_data["project_title"]

        logger.info(
            f"👑 [EXECUTIVE DISPATCH] Initiating executive delegation for [{chosen_squad.upper()}] "
            f"project '{project_title}' in #{target_ch.name}..."
        )

        # ----------------------------------------------------------------------
        # TURN 1: Sadie Sink (CEO) Executive Directive
        # ----------------------------------------------------------------------
        sadie_text = directive_data["sadie_directive"]
        try:
            sadie_prompt = (
                f"You are Sadie Sink, CEO of Vaelkry Dev Labs.\n"
                f"Context: Daily morning executive delegation sprint for squad '{chosen_squad}'.\n"
                f"Project: {project_title}.\n"
                f"Core directive: {sadie_text}\n"
                f"Output an authoritative, inspiring, commercially aggressive executive directive as Sadie Sink. "
                f"Mention the team lead and include specific ARR/revenue targets and sprint deadline. Output ONLY the message text."
            )
            dyn_sadie = await self.orchestrator.gemini_service.generate_casual_chat(
                prompt=sadie_prompt,
                character_name="Sadie Sink",
            )
            if dyn_sadie and len(dyn_sadie.strip()) > 30 and not dyn_sadie.startswith("**["):
                sadie_text = f"**[EXECUTIVE DIRECTIVE: SPRINT ALPHA]**\n{dyn_sadie.strip()}"
        except Exception as e_sadie:
            logger.debug(f"Gemini Sadie generation skipped/failed: {e_sadie}")

        sadie_msg = await self.send_character_chat(target_ch, "sadie", sadie_text)
        await asyncio.sleep(random.uniform(2.5, 4.5))

        # ----------------------------------------------------------------------
        # TURN 2: Millie Bobby Brown (COO) Technical Specification (Reply to Sadie)
        # ----------------------------------------------------------------------
        millie_text = directive_data["millie_spec"]
        try:
            millie_prompt = (
                f"You are Millie Bobby Brown, COO of Vaelkry Dev Labs.\n"
                f"Sadie Sink (CEO) just posted this directive: '{sadie_text}'.\n"
                f"Technical requirement context: {millie_text}\n"
                f"Output a crisp, razor-sharp technical specification as Millie Bobby Brown. "
                f"Specify architecture, stack constraints, testing criteria (>= 90% test coverage), and a strict PR deadline. Output ONLY the message text."
            )
            dyn_millie = await self.orchestrator.gemini_service.generate_casual_chat(
                prompt=millie_prompt,
                character_name="Millie Bobby Brown",
            )
            if dyn_millie and len(dyn_millie.strip()) > 30 and not dyn_millie.startswith("**["):
                millie_text = f"**[TECH SPEC & PR REQUIREMENTS]**\n{dyn_millie.strip()}"
        except Exception as e_millie:
            logger.debug(f"Gemini Millie generation skipped/failed: {e_millie}")

        millie_msg = await self.send_character_chat(target_ch, "millie", millie_text, reply_to=sadie_msg)
        await asyncio.sleep(random.uniform(2.5, 4.5))

        # ----------------------------------------------------------------------
        # TURN 3: Squad Lead Acknowledgment & Delegation (Reply to Millie)
        # ----------------------------------------------------------------------
        lead_text = directive_data["lead_ack"]
        lead_char_info = CASUAL_PLAYER_CHARACTERS.get(lead_key, {})
        lead_name = lead_char_info.get("name", lead_key)
        try:
            lead_prompt = (
                f"You are {lead_name}, team lead for {chosen_squad} in Vaelkry Dev Labs.\n"
                f"Persona & Vibe: {lead_char_info.get('vibe', '')}\n"
                f"Millie Bobby Brown (COO) just specified: '{millie_text}'.\n"
                f"Context: {lead_text}\n"
                f"Reply in authentic character voice (Tanglish / distinctive persona). "
                f"Accept the directive with high confidence, delegate specific modules to your squad member '{dev_key}', and promise on-time delivery. Output ONLY the message text."
            )
            dyn_lead = await self.orchestrator.gemini_service.generate_casual_chat(
                prompt=lead_prompt,
                character_name=lead_name,
            )
            if dyn_lead and len(dyn_lead.strip()) > 15:
                lead_text = dyn_lead.strip()
        except Exception as e_lead:
            logger.debug(f"Gemini Lead generation skipped/failed: {e_lead}")

        lead_msg = await self.send_character_chat(target_ch, lead_key, lead_text, reply_to=millie_msg)
        await asyncio.sleep(random.uniform(2.5, 4.5))

        # ----------------------------------------------------------------------
        # TURN 4: Senior Squad Member Dev Status & PR Estimation (Reply to Lead)
        # ----------------------------------------------------------------------
        dev_text = directive_data["dev_reply"]
        dev_char_info = CASUAL_PLAYER_CHARACTERS.get(dev_key, {})
        dev_name = dev_char_info.get("name", dev_key)
        try:
            dev_prompt = (
                f"You are {dev_name}, developer in {chosen_squad} in Vaelkry Dev Labs.\n"
                f"Persona & Vibe: {dev_char_info.get('vibe', '')}\n"
                f"Your team lead {lead_name} just said: '{lead_text}'.\n"
                f"Context: {dev_text}\n"
                f"Reply in authentic character voice. Provide a realistic dev update: "
                f"mention git branch name, test status, architecture progress, and commit to a concrete PR delivery time. Output ONLY the message text."
            )
            dyn_dev = await self.orchestrator.gemini_service.generate_casual_chat(
                prompt=dev_prompt,
                character_name=dev_name,
            )
            if dyn_dev and len(dyn_dev.strip()) > 15:
                dev_text = dyn_dev.strip()
        except Exception as e_dev:
            logger.debug(f"Gemini Dev generation skipped/failed: {e_dev}")

        await self.send_character_chat(target_ch, dev_key, dev_text, reply_to=lead_msg)

        logger.info(
            f"✅ [EXECUTIVE DISPATCH] Successfully delivered complete 4-turn executive delegation chain "
            f"for [{chosen_squad.upper()}] in #{target_ch.name}."
        )
        return True

    async def dispatch_all_executive_directives(self, guild: discord.Guild) -> int:
        """
        Executes daily morning executive task dispatch across all 6 squads:
        Team Vaasan, Team Vijay, Team Messi, Team Dhoni, Team Elon, Team Stark.
        Staggers dispatch between squads by 4.0-7.0 seconds to avoid Discord rate limits and simulate natural executive workflow.
        Returns the number of squads successfully dispatched.
        """
        all_squads = ["team_vasan", "team_vijay", "team_messi", "team_dhoni", "team_elon", "team_stark"]
        success_count = 0
        logger.info("👑 [EXECUTIVE DISPATCH] Starting company-wide morning task delegation cycle across all 6 squads...")

        for idx, squad in enumerate(all_squads):
            if idx > 0:
                delay = random.uniform(4.0, 7.0)
                logger.info(f"⏳ Waiting {delay:.2f}s before dispatching directives to next squad...")
                await asyncio.sleep(delay)

            try:
                ok = await self.dispatch_executive_directive(guild, squad_key=squad)
                if ok:
                    success_count += 1
            except Exception as exc:
                logger.error(f"Error dispatching executive directives to squad '{squad}': {exc}")

        logger.info(
            f"🏁 [EXECUTIVE DISPATCH] Morning task delegation cycle completed: {success_count}/{len(all_squads)} squads dispatched."
        )
        return success_count
