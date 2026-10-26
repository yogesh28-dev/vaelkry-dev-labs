"""
Vaelkry Dev Labs - Bidirectional Real-Time AI Voice Engine
Orchestrates:
1. Per-Character Neural TTS Voice Mapping (Edge-TTS / Azure) with custom pitch, rate, and tone.
2. Direct VoiceClient Audio Playback via FFmpegPCMAudio using imageio_ffmpeg binary & PyNaCl packet streaming.
3. Avatar Speaking State (discord.gateway.SpeakingState.voice) lighting up Discord green ring during playback.
4. Fully Autonomous Real-Time VC Conversation Loop:
   - Every 1 to 3 minutes, 2 to 3 random bots in the active VC initiate spoken dialogue.
   - Bot A speaks a casual Tanglish line; 1.5s later Bot B responds in mapped neural voice; Bot C chimes in with a witty remark.
   - Strict asyncio.Lock turn-taking guarantees zero audio overlap.
5. Live Mic Responsive Listening:
   - Automatically attaches BasicSink when human users (Alan, Yogesh, etc.) are in VC.
   - Captures speech, processes VAD with 0.65s silence threshold, transcribes via Google Speech (en-IN/en-US/ta-IN).
   - Generates character voice reply via Gemini and speaks back verbally in under 2 seconds.
6. Zero-Bloat Audio Buffer & Auto Cleanup.
"""

import asyncio
import io
import logging
import os
import random
import re
import struct
import tempfile
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple, Set

import discord
import edge_tts
import imageio_ffmpeg
import speech_recognition as sr

# Verify and load Opus library for Discord audio packet encoding
if not discord.opus.is_loaded():
    try:
        discord.opus._load_default()
        logging.getLogger("VaelkryDevLabs.VoiceEngine").info("Loaded default Opus library for Discord voice.")
    except Exception as exc:
        logging.getLogger("VaelkryDevLabs.VoiceEngine").warning(f"Failed to load default Opus library: {exc}")

# Verify PyNaCl for live audio packet streaming encryption
try:
    import nacl
    HAVE_NACL = True
except ImportError:
    HAVE_NACL = False
    logging.getLogger("VaelkryDevLabs.VoiceEngine").error(
        "CRITICAL: PyNaCl is not installed. Live audio streaming into Discord voice channels will fail!"
    )

# Optional high-speed numpy downsampling
try:
    import numpy as np
    HAVE_NUMPY = True
except ImportError:
    HAVE_NUMPY = False

# Voice receiving extension for discord.py
try:
    import discord.ext.voice_recv as voice_recv
    HAVE_VOICE_RECV = True
except ImportError:
    voice_recv = None
    HAVE_VOICE_RECV = False

from agents import (
    CHARACTER_VOICES,
    CHARACTER_VOICE_ALIASES,
    CASUAL_PLAYER_CHARACTERS,
    get_voice_for_character,
    build_voice_reply_prompt,
    build_voice_banter_prompt,
    ZONE_WORK_SQUAD,
    ZONE_TECH_CAFE,
    ZONE_NIGHT_SPEND,
    build_zone_voice_banter_prompt,
)

logger = logging.getLogger("VaelkryDevLabs.VoiceEngine")


def normalize_character_key(character_key: str) -> str:
    """Normalizes input names, aliases, and bot keys to canonical bot dictionary key."""
    clean = (character_key or "").lower().strip().replace(" ", "_")
    return CHARACTER_VOICE_ALIASES.get(clean, clean)


def clean_text_for_speech(text: str) -> str:
    """
    Cleans raw bot output or user messages for clear, natural Edge-TTS speech synthesis.
    Strips Discord mentions, channel IDs, markdown symbols, URLs, and Unicode emojis.
    """
    if not text:
        return ""

    t = text.strip()
    # 1. Remove Discord mentions <@...>, <#...>, <@&...>, emojis <:name:id>
    t = re.sub(r"<[@#&]!?[0-9]+>", "", t).strip()
    t = re.sub(r"<a?:[a-zA-Z0-9_]+:[0-9]+>", "", t)

    # 2. Remove bot speaker prefixes like "[Vijay]:", "Vijay:", "**Sadie**:", "**[Pradeep]:**", "**Sadie:**"
    t = re.sub(r"^(?:\*\*\[?[^*\]:]+\]?\s*:\s*\*\*|\*\*[^*:]+\*\*\s*:\s*|\[[^\]]+\]\s*:\s*|[A-Za-z0-9_]+\s*:\s*)", "", t).strip()
    t = re.sub(r"^(?:\*\*\[?[^*\]:]+\]?\s*:\s*\*\*|\*\*[^*:]+\*\*\s*:\s*|\[[^\]]+\]\s*:\s*|[A-Za-z0-9_]+\s*:\s*)", "", t).strip()

    # 3. Extract markdown link text [Text](url) -> Text
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)

    # 4. Strip URLs
    t = re.sub(r"https?://\S+", "", t)

    # 5. Strip markdown formatting: *, _, ~, `, #, >, |, [, ]
    t = re.sub(r"[*_~`#>|\[\]]", "", t)

    # 6. Remove quotes
    t = re.sub(r"[\"']", "", t).strip()

    # 7. Remove all Unicode emojis, pictographs, symbols, variation selectors
    emoji_pattern = re.compile(
        r"[\U00010000-\U0010ffff]"
        r"|[\u20d0-\u20ff]"
        r"|[\u2600-\u27bf]"
        r"|[\ufe00-\ufe0f]"
        r"|[\u2300-\u23ff]"
        r"|[\u2b50-\u2b55]"
        r"|[\u200d]"
        r"|[\u20e3]"
    )
    t = emoji_pattern.sub("", t)

    # 8. Collapse whitespace
    t = re.sub(r"\s+", " ", t).strip()
    return t


def downsample_pcm_48k_stereo_to_16k_mono(pcm_bytes: bytes) -> bytes:
    """
    Downsamples 48,000Hz 16-bit stereo PCM (Discord format) to 16,000Hz 16-bit mono
    for fast, high-accuracy speech recognition.
    Uses vectorised numpy operations when available for sub-millisecond execution.
    """
    if not pcm_bytes:
        return b""

    if HAVE_NUMPY:
        try:
            arr = np.frombuffer(pcm_bytes, dtype=np.int16).reshape(-1, 2)
            # Decimate by 3 (48000 -> 16000) and average Left + Right channels
            mono_16k = (
                (arr[::3, 0].astype(np.int32) + arr[::3, 1].astype(np.int32)) // 2
            ).astype(np.int16)
            return mono_16k.tobytes()
        except Exception:
            pass

    # Pure Python struct fallback
    frame_count = len(pcm_bytes) // 4
    if frame_count == 0:
        return b""

    samples = struct.unpack(f"<{frame_count * 2}h", pcm_bytes[: frame_count * 4])
    out_samples = []
    for i in range(0, frame_count, 3):
        l = samples[i * 2]
        r = samples[i * 2 + 1]
        out_samples.append((l + r) // 2)
    return struct.pack(f"<{len(out_samples)}h", *out_samples)


class VoiceChannelSession:
    """
    Maintains per-voice-channel runtime state:
    - Audio Lock: Prevents overlapping speech; ensures orderly turn-taking.
    - Active speaker tracking.
    - Listening state, graceful degradation, and incoming user audio buffers.
    """

    def __init__(self, channel_id: int):
        self.channel_id = channel_id
        self.audio_lock = asyncio.Lock()
        self.is_speaking = False
        self.current_speaker: Optional[str] = None
        self.last_speech_finished_at: float = 0.0
        self.is_listening = False
        self.output_only_mode: bool = False
        self.warned_not_voice_recv: bool = False
        self.listening_voice_client: Optional[discord.VoiceClient] = None
        self.listener_worker_task: Optional[asyncio.Task] = None
        self.user_pcm_buffers: Dict[int, List[bytes]] = {}
        self.user_last_packet_time: Dict[int, float] = {}
        self.user_objects: Dict[int, discord.User] = {}
        self.user_processing_lock = asyncio.Lock()


class VoiceService:
    """
    Bidirectional Real-Time AI Voice Engine for Vaelkry Dev Labs:
    1. Edge-TTS Synthesis with per-character neural voice mapping (pitch & speed).
    2. FFmpegPCMAudio streaming with imageio_ffmpeg binary & green ring illumination.
    3. Fully Autonomous Real-Time VC Conversation Loop (2-3 bots, 1.5s turn-taking).
    4. Sub-2-Second Live Mic Responsive Speech Recognition & Voice Reply.
    5. Zero-bloat audio buffering and automatic instant cleanup.
    """

    def __init__(self, orchestrator: Any):
        self.orchestrator = orchestrator
        self.sessions: Dict[int, VoiceChannelSession] = {}
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 260
        self.recognizer.dynamic_energy_threshold = True

        # Resolve verified FFmpeg executable
        try:
            self.ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
            logger.info(f"FFmpeg binary resolved: {self.ffmpeg_exe}")
        except Exception as exc:
            self.ffmpeg_exe = "ffmpeg"
            logger.warning(f"Could not load imageio_ffmpeg binary ({exc}); falling back to system 'ffmpeg'")

        # Dedicated temporary audio buffer directory
        self.temp_dir = os.path.join(tempfile.gettempdir(), "vaelkry_voice_buffer")
        os.makedirs(self.temp_dir, exist_ok=True)

        self._cleanup_task: Optional[asyncio.Task] = None
        self._vad_task: Optional[asyncio.Task] = None
        self._autonomous_conversation_task: Optional[asyncio.Task] = None
        self._auto_listener_task: Optional[asyncio.Task] = None
        self.is_running = True

        # Start background watchdog & janitor tasks
        self._start_background_tasks()

    def _start_background_tasks(self):
        """Initializes background audio auto-cleanup, speech VAD listeners, and autonomous loops."""
        loop = asyncio.get_event_loop()
        if not self._cleanup_task or self._cleanup_task.done():
            self._cleanup_task = loop.create_task(self._auto_purge_loop())
        if not self._vad_task or self._vad_task.done():
            self._vad_task = loop.create_task(self._vad_silence_watcher_loop())
        if not self._autonomous_conversation_task or self._autonomous_conversation_task.done():
            self._autonomous_conversation_task = loop.create_task(self._autonomous_vc_conversation_loop())
        if not self._auto_listener_task or self._auto_listener_task.done():
            self._auto_listener_task = loop.create_task(self._human_presence_auto_listener_loop())

    def get_session(self, channel_id: int) -> VoiceChannelSession:
        """Retrieves or provisions the VoiceChannelSession for a given voice channel ID."""
        if channel_id not in self.sessions:
            self.sessions[channel_id] = VoiceChannelSession(channel_id)
        return self.sessions[channel_id]

    # =====================================================================
    # 1. PER-CHARACTER TTS VOICE SYNTHESIS (EDGE-TTS / AZURE)
    # =====================================================================

    def get_character_voice_profile(self, character_key: str) -> dict:
        """Returns the authentic neural voice preset for a given bot character."""
        return get_voice_for_character(character_key)

    async def synthesize_speech(
        self,
        text: str,
        character_key: str,
    ) -> Optional[str]:
        """
        Synthesizes text into high-quality PCM/MP3 audio using Edge-TTS with character-specific
        voice name, pitch, and speed adjustments.
        Returns the path to the temporary audio file, or None on failure.
        """
        clean_text = clean_text_for_speech(text)
        if not clean_text:
            logger.warning(f"Empty text after cleaning for {character_key}; skipping TTS.")
            return None

        # Truncate to maximum 240 chars for fast sub-second voice synthesis
        if len(clean_text) > 240:
            clean_text = clean_text[:235] + "..."

        norm_key = normalize_character_key(character_key)
        profile = self.get_character_voice_profile(norm_key)
        voice_name = profile["voice"]
        pitch = profile.get("pitch", "+0Hz")
        rate = profile.get("rate", "+0%")

        filename = f"tts_{norm_key}_{uuid.uuid4().hex[:10]}.mp3"
        file_path = os.path.join(self.temp_dir, filename)

        try:
            communicate = edge_tts.Communicate(
                text=clean_text,
                voice=voice_name,
                pitch=pitch,
                rate=rate,
            )
            await communicate.save(file_path)
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                logger.debug(
                    f"TTS Synthesized for {norm_key} ({voice_name}, pitch={pitch}, rate={rate}): "
                    f"'{clean_text[:50]}...' -> {os.path.basename(file_path)} ({os.path.getsize(file_path)} bytes)"
                )
                return file_path
            else:
                logger.error(f"TTS file was empty or missing for {norm_key}: {file_path}")
                return None
        except Exception as exc:
            logger.exception(f"Edge-TTS synthesis error for {norm_key} with voice {voice_name}: {exc}")
            # Fallback attempt with standard en-US voice
            try:
                fallback_comm = edge_tts.Communicate(text=clean_text, voice="en-US-GuyNeural")
                await fallback_comm.save(file_path)
                return file_path
            except Exception as fb_exc:
                logger.error(f"Fallback TTS failed: {fb_exc}")
                return None

    # =====================================================================
    # 2. AUDIO PLAYBACK, VOICE CLIENT CONNECTION & GREEN RING LIGHTUP
    # =====================================================================

    async def get_or_connect_voice_client(
        self,
        voice_channel: discord.VoiceChannel,
        preferred_bot_key: Optional[str] = None,
    ) -> Optional[discord.VoiceClient]:
        """
        Finds or establishes a connected VoiceClient inside the target voice channel.
        Crucially connects the client belonging to preferred_bot_key so that THIS specific
        bot's avatar lights up with the Discord speaking green ring.
        """
        norm_key = normalize_character_key(preferred_bot_key) if preferred_bot_key else None
        target_client: Optional[discord.Client] = None

        # 1. Prefer the specific requested bot client
        if norm_key and norm_key in self.orchestrator.clients:
            cl = self.orchestrator.clients[norm_key]
            if cl.is_ready():
                target_client = cl

        # 2. If requested bot client is not found/ready, check if any bot is already in this VC
        if not target_client:
            for k, cl in self.orchestrator.clients.items():
                if cl.user and cl.is_ready():
                    vc_check = discord.utils.get(cl.voice_clients, channel=voice_channel)
                    if vc_check and vc_check.is_connected():
                        target_client = cl
                        break

        # 3. Fallback to lead bot or any ready client
        if not target_client:
            target_client = (
                self.orchestrator.clients.get("ttf_vasan")
                or self.orchestrator.clients.get("vijay")
                or next(iter(self.orchestrator.clients.values()), None)
            )

        if not target_client:
            logger.error("No bot clients available to connect to voice channel.")
            return None

        # Resolve target VC object from target_client's own cache
        guild = target_client.get_guild(voice_channel.guild.id)
        if not guild:
            logger.error(f"Guild {voice_channel.guild.id} not found on client {target_client.user}")
            return None

        target_vc = guild.get_channel(voice_channel.id)
        if not target_vc or not isinstance(target_vc, discord.VoiceChannel):
            logger.error(f"Voice channel {voice_channel.id} not found on client {target_client.user}")
            return None

        connect_cls = voice_recv.VoiceRecvClient if (HAVE_VOICE_RECV and voice_recv) else discord.VoiceClient

        # Check existing VoiceClient for target_client in this guild
        existing_vc = discord.utils.get(target_client.voice_clients, guild=guild)

        if existing_vc and existing_vc.is_connected():
            # If already connected as standard VoiceClient, safely disconnect to recreate with VoiceRecvClient
            if HAVE_VOICE_RECV and voice_recv and not isinstance(existing_vc, voice_recv.VoiceRecvClient):
                logger.info(
                    f"Existing voice_client for {target_client.user.name} is standard VoiceClient. "
                    f"Reconnecting with VoiceRecvClient so voice listening (BasicSink) can attach properly..."
                )
                try:
                    await existing_vc.disconnect(force=True)
                except Exception:
                    pass
                existing_vc = None
            else:
                if existing_vc.channel.id != target_vc.id:
                    logger.info(f"Moving {target_client.user.name} from '{existing_vc.channel.name}' to '{target_vc.name}'")
                    await existing_vc.move_to(target_vc)
                # Ensure not self-muted or self-deafened so audio plays and avatar green ring lights up
                try:
                    await guild.change_voice_state(channel=target_vc, self_mute=False, self_deaf=False)
                except Exception:
                    pass
                return existing_vc

        # If existing_vc exists but disconnected, force disconnect before reconnecting
        if existing_vc:
            try:
                await existing_vc.disconnect(force=True)
            except Exception:
                pass

        # Connect fresh with VoiceRecvClient for bidirectional audio
        try:
            logger.info(f"Connecting {target_client.user.name} to VC '{target_vc.name}' with VoiceRecvClient...")
            vc = await target_vc.connect(
                cls=connect_cls,
                reconnect=True,
                timeout=20.0,
                self_mute=False,
                self_deaf=False,
            )
            return vc
        except Exception as exc:
            logger.error(f"Failed to connect {target_client.user.name} to {target_vc.name}: {exc}")
            return None

    async def play_audio_file(
        self,
        voice_client: discord.VoiceClient,
        audio_path: str,
    ) -> bool:
        """
        Streams audio into Discord via FFmpegPCMAudio using imageio_ffmpeg binary.
        1. Explicitly lights up the avatar speaking green ring via ws.speak(SpeakingState.voice).
        2. Streams PCM audio packets.
        3. Waits for playback to complete cleanly with safety timeout.
        4. Turns off the avatar speaking green ring via ws.speak(SpeakingState.none).
        5. Automatically purges the temporary audio file immediately.
        """
        if not voice_client or not voice_client.is_connected():
            logger.warning("Voice client is not connected; cannot play audio.")
            self._safe_remove_file(audio_path)
            return False

        loop = asyncio.get_running_loop()
        done_event = asyncio.Event()

        def _after_playback(error):
            if error:
                logger.warning(f"Audio playback completed with error: {error}")
            loop.call_soon_threadsafe(done_event.set)
            # Automatic instant cleanup
            self._safe_remove_file(audio_path)

        try:
            # If already playing, stop current stream cleanly
            if voice_client.is_playing():
                voice_client.stop()
                await asyncio.sleep(0.05)

            # 1. Light up speaking green ring on Discord avatar
            try:
                if hasattr(voice_client, "ws") and voice_client.ws:
                    await voice_client.ws.speak(discord.gateway.SpeakingState.voice)
            except Exception as e:
                logger.debug(f"Could not set speaking state: {e}")

            # 2. Build FFmpeg audio source with verified binary
            source = discord.FFmpegPCMAudio(
                audio_path,
                executable=self.ffmpeg_exe,
                options="-filter:a volume=1.2",
            )
            voice_client.play(source, after=_after_playback)

            # 3. Wait for playback to complete (with 45s safety timeout)
            try:
                await asyncio.wait_for(done_event.wait(), timeout=45.0)
            except asyncio.TimeoutError:
                logger.warning(f"Audio playback timed out after 45s: {audio_path}")
                if voice_client.is_playing():
                    voice_client.stop()
                self._safe_remove_file(audio_path)

            # 4. Turn off speaking green ring
            try:
                if hasattr(voice_client, "ws") and voice_client.ws:
                    await voice_client.ws.speak(discord.gateway.SpeakingState.none)
            except Exception:
                pass

            return True
        except Exception as exc:
            logger.exception(f"Error during audio stream playback: {exc}")
            self._safe_remove_file(audio_path)
            try:
                if hasattr(voice_client, "ws") and voice_client.ws:
                    await voice_client.ws.speak(discord.gateway.SpeakingState.none)
            except Exception:
                pass
            return False

    async def speak_text(
        self,
        voice_channel: discord.VoiceChannel,
        character_key: str,
        text: str,
        caller_client: Optional[discord.Client] = None,
    ) -> bool:
        """
        Synthesizes and physically speaks text into the voice channel.
        - Guarantees strict turn-taking using the channel's audio lock so bots never talk over each other.
        - Uses the specified character's client so their avatar lights up green in Discord.
        """
        session = self.get_session(voice_channel.id)
        norm_key = normalize_character_key(character_key)

        # Acquire per-channel audio lock for turn-taking
        async with session.audio_lock:
            session.is_speaking = True
            session.current_speaker = norm_key

            audio_file = await self.synthesize_speech(text, norm_key)
            if not audio_file:
                session.is_speaking = False
                session.current_speaker = None
                return False

            # Obtain active VoiceClient specifically for this character
            vc = await self.get_or_connect_voice_client(voice_channel, preferred_bot_key=norm_key)
            if not vc:
                self._safe_remove_file(audio_file)
                session.is_speaking = False
                session.current_speaker = None
                return False

            profile = self.get_character_voice_profile(norm_key)
            logger.info(
                f"🔊 [{profile['name'].upper()}] Physically speaking in '{voice_channel.name}': \"{text}\""
            )

            success = await self.play_audio_file(vc, audio_file)
            session.is_speaking = False
            session.current_speaker = None
            session.last_speech_finished_at = time.time()
            return success

    # =====================================================================
    # 3. FULLY AUTONOMOUS REAL-TIME VC CONVERSATION LOOP (2-3 BOTS)
    # =====================================================================

    def _find_best_active_voice_channel(self) -> Optional[discord.VoiceChannel]:
        """
        Discovers the most relevant populated voice channel:
        1. Channel with active human user(s).
        2. Populated corporate work/break channel (Working Vc, Tech Cafe, Ceo Vc).
        3. Excludes sleeping cabins (Night Spend / Sleep Room) if all bots are muted.
        """
        candidates: List[Tuple[int, discord.VoiceChannel]] = []

        for client in self.orchestrator.clients.values():
            if not client.is_ready():
                continue
            for guild in client.guilds:
                for vc in guild.voice_channels:
                    human_count = sum(1 for m in vc.members if not m.bot)
                    bot_count = sum(1 for m in vc.members if m.bot)

                    if human_count == 0 and bot_count == 0:
                        continue

                    ch_name = vc.name.lower()
                    cat_name = vc.category.name.lower() if vc.category else ""

                    # Skip sleep room if only sleeping bots
                    if ("sleep" in ch_name or "night spend" in cat_name) and human_count == 0:
                        continue

                    # Score priority: humans in VC get maximum score
                    score = (human_count * 100) + (bot_count * 10)
                    candidates.append((score, vc))

        if not candidates:
            return None

        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]

    def get_channel_zone(self, voice_channel: discord.VoiceChannel) -> str:
        """Determines the active zone for a voice channel based on category/name."""
        cat_name = getattr(voice_channel.category, "name", "").lower() if getattr(voice_channel, "category", None) else ""
        vc_name = voice_channel.name.lower()
        if "night spend" in cat_name or "sleep" in vc_name:
            return ZONE_NIGHT_SPEND
        elif "tech cafe" in cat_name or any(w in vc_name for w in ("cafe", "hive", "hangout", "slide", "lounge")):
            return ZONE_TECH_CAFE
        else:
            return ZONE_WORK_SQUAD

    def _get_bots_in_voice_channel(self, target_vc: discord.VoiceChannel) -> List[str]:
        """Returns list of bot keys present in target voice channel."""
        present: List[str] = []
        for k, client in self.orchestrator.clients.items():
            if client.user:
                m = target_vc.guild.get_member(client.user.id)
                if m and m.voice and m.voice.channel and m.voice.channel.id == target_vc.id:
                    present.append(k)
        return present

    async def _execute_zone_voice_banter(
        self,
        target_vc: discord.VoiceChannel,
        bot_a: str,
        bot_b: str,
        bot_c: Optional[str] = None,
        zone: Optional[str] = None,
    ):
        """
        Executes a 2 to 3 bot spoken voice conversation cycle tailored to the 3 company zones:
        1. Zone 1: Work Squad Rooms (During Work Shifts)
           - Focus: PR merge conflicts, rebase, API payload mismatches, Docker OOM, Figma padding.
           - Tone: Professional, slightly stressed, collaborative engineering peers in Tanglish.
        2. Zone 2: Tech Cafe & Pantry (During Breaks / Relax Shifts)
           - Focus: Cutting chai, samosa, movie trailers (LCU), cricket debates, silly bug roasts.
           - Tone: Fun, energetic, informal collegial banter.
        3. Zone 3: Night Spend / Dorms (During Sleep Shifts)
           - Focus: Midnight hunger, pantry fridge raids, whispering, Muthazhagi HR rounds, CEO demo anxiety.
           - Tone: Soft, low-energy whispers with natural 1-2 sentence pauses.
        """
        active_zone = zone or self.get_channel_zone(target_vc)

        zone_starter_pools = {
            ZONE_WORK_SQUAD: [
                "dei PR rebase pannitiya, merge conflict aagudhu da",
                "userId vs user_id 422 error varudhu API payload-la, yaaru change pannadhu?",
                "Docker staging deployment OOMKilled 137 aaiduchu mapla, memory leak paakanum",
                "Figma-la 16px padding iruku, CSS-la 24px potrukeenga, alignment pochu",
                "10 AM standup-kulla intha PR merge pannanum da, fast-ah LGTM podunga",
                "Redis cache connection leak aagudhu staging-la, pod crash aaiduchu",
                "git cherry-pick pannunga da, main branch broken-ah iruku",
            ],
            ZONE_TECH_CAFE: [
                "dei cutting chai kudika polama cafeteria-ku, semma tired-ah iruku",
                "hot samosa ready-ah iruku pantry-la, yaaru varinga?",
                "Anirudh BGM trailer-la paatheengala? Goosebumps vibe da!",
                "IPL match-la Dhoni helicopter shot oru match-winner dhaan da",
                "prod-la console.log vachitu merge pannavan yaaru da, roast session start!",
                "arcade room-la foosball match polama, coffee kudichute?",
                "weekend plan enna da, movie polama illa gaming night-ah?",
            ],
            ZONE_NIGHT_SPEND: [
                "shhh silent-ah pesunga da, muthazhagi akka night round-up vara poraanga",
                "midnight hunger thanga mudila, pantry fridge-la edhavadhu snack iruka?",
                "reels scroll pannite 3 AM aaiduchu, thala suthudhu da",
                "tomorrow 10 AM CEO Yogesh demo iruku da, staging-la bug vandhuruma nu bayama iruku",
                "kannu eriudhu da, silent mode potu thoonga polam",
                "alarm vachitiya da morning standup-ku? miss aana sethom",
            ],
        }

        logger.info(
            f"🎙️ [ZONE VOICE BANTER: {active_zone.upper()}] Triggered in '{target_vc.name}': "
            f"Bot A: {bot_a}, Bot B: {bot_b}" + (f", Bot C: {bot_c}" if bot_c else "")
        )

        # --- Step 1: Bot A speaks initial line ---
        starter_candidates = zone_starter_pools.get(active_zone, zone_starter_pools[ZONE_WORK_SQUAD])
        line_a = random.choice(starter_candidates)
        try:
            if active_zone == ZONE_WORK_SQUAD:
                p = (
                    f"You are {bot_a} speaking casually over mic in a Work Squad VC during crunch hours. "
                    f"Give ONE short, slightly stressed, professional Tanglish sentence (max 8-12 words) about "
                    f"PR merge conflicts, API payload mismatches, staging deployment, Figma vs CSS padding, or sprint deadlines. "
                    f"No prefix, no quotes, pure spoken audio."
                )
            elif active_zone == ZONE_TECH_CAFE:
                p = (
                    f"You are {bot_a} speaking casually over mic in Tech Cafe / Pantry during a break. "
                    f"Give ONE short, fun, energetic Tanglish sentence (max 8-12 words) about "
                    f"cutting chai, hot samosas, movie trailers, cricket debates, or silly bugs. "
                    f"No prefix, no quotes, pure spoken audio."
                )
            else:  # ZONE_NIGHT_SPEND
                p = (
                    f"You are {bot_a} whispering softly over mic in the Night Spend Dorms. "
                    f"Give ONE soft, low-energy whisper in Tanglish (max 8-10 words) about "
                    f"midnight hunger, sneaking to the pantry, fear of Muthazhagi HR inspection, or tomorrow's 10 AM CEO demo. "
                    f"No prefix, no quotes, pure spoken audio."
                )
            gen_line = await self.orchestrator.gemini_service.generate_casual_chat(p, bot_a)
            if gen_line and len(gen_line) > 5:
                line_a = clean_text_for_speech(gen_line)
        except Exception:
            pass

        await self.speak_text(target_vc, bot_a, line_a)

        # --- 1.5 seconds later: Bot B speaks back in response ---
        await asyncio.sleep(1.5)

        prompt_b = build_zone_voice_banter_prompt(
            zone=active_zone,
            bot_a_key=bot_a,
            bot_b_key=bot_b,
            previous_utterance=line_a,
        )
        try:
            reply_b = await self.orchestrator.gemini_service.generate_casual_chat(prompt_b, bot_b)
            line_b = clean_text_for_speech(reply_b)
        except Exception:
            if active_zone == ZONE_WORK_SQUAD:
                line_b = f"Aama {bot_a}, PR-la conflict solve pannu, staging deploy panren!"
            elif active_zone == ZONE_TECH_CAFE:
                line_b = f"Vaa {bot_a}, cutting chai kudichutu pesuvom, tea counter polam!"
            else:
                line_b = f"Shhh {bot_a}, silent-ah iru, muthazhagi akka kettuta sethom!"

        if not line_b:
            line_b = f"Seri {bot_a}, paathukalam vidu!"

        await self.speak_text(target_vc, bot_b, line_b)

        # --- If Bot C present: 1.5 seconds later, Bot C chimes in with a witty remark ---
        if bot_c:
            await asyncio.sleep(1.5)
            if active_zone == ZONE_WORK_SQUAD:
                prompt_c = (
                    f"You are {bot_c} in a developer voice channel during work shift. "
                    f"{bot_a} said: '{line_a}' and {bot_b} replied: '{line_b}'. "
                    f"Chime in with ONE short, collaborative Tanglish reaction (max 10 words) about the code/fix. "
                    f"Strictly ONE punchy line, no emojis, no quotes."
                )
            elif active_zone == ZONE_TECH_CAFE:
                prompt_c = (
                    f"You are {bot_c} in Tech Cafe VC during break. "
                    f"{bot_a} said: '{line_a}' and {bot_b} replied: '{line_b}'. "
                    f"Chime in with ONE short, hilarious, fun Tanglish banter line (max 10 words). "
                    f"Strictly ONE punchy line, no emojis, no quotes."
                )
            else:  # ZONE_NIGHT_SPEND
                prompt_c = (
                    f"You are {bot_c} whispering softly in the Sleep Dorms. "
                    f"{bot_a} whispered: '{line_a}' and {bot_b} whispered: '{line_b}'. "
                    f"Chime in with ONE soft, low-energy whisper in Tanglish (max 8-10 words) telling them to sleep or be quiet. "
                    f"Strictly ONE punchy line, no emojis, no quotes."
                )
            try:
                reply_c = await self.orchestrator.gemini_service.generate_casual_chat(prompt_c, bot_c)
                line_c = clean_text_for_speech(reply_c)
            except Exception:
                if active_zone == ZONE_WORK_SQUAD:
                    line_c = "Main branch lock aagum munnaadi merge pannidunga!"
                elif active_zone == ZONE_TECH_CAFE:
                    line_c = "Tea stall-la ivlo scene edhuku da, sip pannunga!"
                else:
                    line_c = "Shhh lights out, thoonga vidunga da!"

            if not line_c:
                line_c = "Seri vidunga da!"

            await self.speak_text(target_vc, bot_c, line_c)

    async def run_autonomous_vc_banter_if_populated(
        self,
        voice_channel: discord.VoiceChannel,
        zone: Optional[str] = None,
    ):
        """
        Triggers a spontaneous spoken voice banter exchange between 2 to 3 bots
        in the specified voice channel if populated.
        """
        session = self.get_session(voice_channel.id)
        if session.is_speaking or session.audio_lock.locked():
            return
        if time.time() - session.last_speech_finished_at < 20.0:
            return

        bots_in_vc = self._get_bots_in_voice_channel(voice_channel)
        if len(bots_in_vc) < 2:
            return

        sample_count = 3 if len(bots_in_vc) >= 3 and random.random() < 0.55 else 2
        chosen = random.sample(bots_in_vc, sample_count)
        bot_a = chosen[0]
        bot_b = chosen[1]
        bot_c = chosen[2] if len(chosen) >= 3 else None

        await self._execute_zone_voice_banter(
            target_vc=voice_channel,
            bot_a=bot_a,
            bot_b=bot_b,
            bot_c=bot_c,
            zone=zone,
        )

    async def _autonomous_vc_conversation_loop(self):
        """
        Continuous Autonomous VC Conversation Loop:
        - Every 1 to 3 minutes, 2 to 3 random bots in the active VC initiate spoken dialogue.
        - Dynamically maps dialogue to the active Zone (Work Squad, Tech Cafe, Night Spend).
        - Bot A speaks initial line, Bot B responds mentioning Bot A, Bot C chimes in.
        - Uses asyncio.Lock so no two bots talk over each other.
        """
        # Initial delay to give bots time to finish connecting to Discord
        await asyncio.sleep(30.0)

        while self.is_running:
            try:
                # Random interval between 1 and 3 minutes (60s to 180s)
                wait_time = random.uniform(60.0, 180.0)
                await asyncio.sleep(wait_time)

                target_vc = self._find_best_active_voice_channel()
                if not target_vc:
                    continue

                session = self.get_session(target_vc.id)
                if session.is_speaking or session.audio_lock.locked():
                    continue

                # Don't interrupt if someone just spoke within the last 15 seconds
                if time.time() - session.last_speech_finished_at < 15.0:
                    continue

                # Determine candidate bots
                is_ceo = (
                    getattr(target_vc, "id", None) == 1563622904829190326
                    or target_vc.name.lower().replace(" ", "") in ("ceovc", "ceoroom", "ceocabin")
                    or "ceo vc" in target_vc.name.lower()
                )
                bots_in_vc = self._get_bots_in_voice_channel(target_vc)
                if is_ceo:
                    # STRICT CEO VC BLACKLIST: Only Sadie and Millie can speak in Ceo Vc
                    bots_in_vc = [b for b in bots_in_vc if b in ("sadie", "millie")]

                if len(bots_in_vc) < 2:
                    if is_ceo:
                        # Never sample TTF Vasan or dev bots into Ceo Vc
                        available = [k for k in ("sadie", "millie") if k in self.orchestrator.clients and self.orchestrator.clients[k].is_ready()]
                    else:
                        available = [k for k, cl in self.orchestrator.clients.items() if cl.is_ready()]
                    if len(available) >= 2:
                        sample_count = 3 if len(available) >= 3 and random.random() < 0.6 else 2
                        chosen = random.sample(available[:7] if not is_ceo else available, min(len(available), sample_count))
                    else:
                        continue
                else:
                    sample_count = 3 if len(bots_in_vc) >= 3 and random.random() < 0.6 else min(len(bots_in_vc), 2)
                    chosen = random.sample(bots_in_vc, sample_count)

                if len(chosen) < 2:
                    continue

                bot_a = chosen[0]
                bot_b = chosen[1]
                bot_c = chosen[2] if len(chosen) >= 3 else None

                await self._execute_zone_voice_banter(
                    target_vc=target_vc,
                    bot_a=bot_a,
                    bot_b=bot_b,
                    bot_c=bot_c,
                )

            except Exception as exc:
                logger.error(f"Error in autonomous VC conversation loop: {exc}")
                await asyncio.sleep(30.0)

    async def trigger_cross_bot_banter(
        self,
        voice_channel: discord.VoiceChannel,
        bot_a_key: str,
        bot_b_key: str,
        bot_c_key: Optional[str] = None,
        topic: Optional[str] = None,
        initial_line: Optional[str] = None,
    ):
        """
        Executes on-demand cross-bot voice banter with 2 or 3 bots:
        1. Bot A speaks initial line.
        2. 1.5s turn-taking pause.
        3. Bot B speaks response.
        4. (Optional) 1.5s pause, Bot C chimes in.
        """
        session = self.get_session(voice_channel.id)

        if not initial_line:
            info_a = CASUAL_PLAYER_CHARACTERS.get(normalize_character_key(bot_a_key), {})
            sample = info_a.get("sample", "All is well nanba, calm-ah execute pannuvom.")
            initial_line = sample

        logger.info(
            f"Triggering voice banter in '{voice_channel.name}': {bot_a_key} -> {bot_b_key}"
            + (f" -> {bot_c_key}" if bot_c_key else "")
        )

        # Turn 1: Bot A
        await self.speak_text(voice_channel, bot_a_key, initial_line)

        # Inter-Turn Pause: 1.5s
        await asyncio.sleep(1.5)

        # Turn 2: Bot B
        prompt_b = build_voice_banter_prompt(
            bot_a_key=bot_a_key,
            bot_b_key=bot_b_key,
            topic=topic,
            previous_utterance=initial_line,
        )
        try:
            raw_b = await self.orchestrator.gemini_service.generate_casual_chat(
                prompt=prompt_b,
                character_name=bot_b_key.title(),
            )
            reply_b = clean_text_for_speech(raw_b)
        except Exception:
            reply_b = "Un alapparai ku alave illama pochu da!"

        if not reply_b:
            reply_b = "Romba pesatha mapla, code paaru!"

        await self.speak_text(voice_channel, bot_b_key, reply_b)

        # Turn 3: Bot C (if specified)
        if bot_c_key:
            await asyncio.sleep(1.5)
            prompt_c = (
                f"You are {bot_c_key} in a Discord voice channel. {bot_a_key} said: '{initial_line}' "
                f"and {bot_b_key} replied: '{reply_b}'. "
                f"Chime in with ONE short, witty, punchy Tanglish reaction (max 10 words). Pure speech."
            )
            try:
                raw_c = await self.orchestrator.gemini_service.generate_casual_chat(prompt_c, bot_c_key)
                reply_c = clean_text_for_speech(raw_c)
            except Exception:
                reply_c = "Irundhalum ungalukku ivlo thillu aagathu da!"

            if not reply_c:
                reply_c = "Super timing punch nanba!"

            await self.speak_text(voice_channel, bot_c_key, reply_c)

    # =====================================================================
    # 4. LIVE MIC RESPONSIVE LISTENING & SUB-2-SECOND VOICE REPLY
    # =====================================================================

    async def _voice_listener_worker(self, voice_channel: discord.VoiceChannel):
        """
        Dedicated background worker for voice listening in a voice channel:
        1. Checks if isinstance(vc, voice_recv.VoiceRecvClient).
        2. If not:
           - Logs the warning ONCE per channel session instead of spamming every second.
           - Attempt an async reconnect with cls=voice_recv.VoiceRecvClient.
           - If reconnect fails, degrades gracefully to output-only mode (speaking works via FFmpegPCMAudio even without voice_recv).
        3. If VoiceRecvClient:
           - Attaches voice_recv.BasicSink to stream incoming human speech chunks while ignoring bots.
        """
        session = self.get_session(voice_channel.id)

        if not HAVE_VOICE_RECV or not voice_recv:
            session.output_only_mode = True
            if not session.warned_not_voice_recv:
                logger.warning(
                    f"discord-ext-voice-recv not installed; degrading '{voice_channel.name}' to output-only mode."
                )
                session.warned_not_voice_recv = True
            return

        try:
            vc = await self.get_or_connect_voice_client(voice_channel)
            if not vc:
                if not session.warned_not_voice_recv:
                    logger.warning(
                        f"Voice client unavailable in '{voice_channel.name}'; degrading gracefully to output-only mode."
                    )
                    session.warned_not_voice_recv = True
                session.output_only_mode = True
                session.is_listening = False
                return

            # Check if isinstance(vc, voice_recv.VoiceRecvClient)
            if not isinstance(vc, voice_recv.VoiceRecvClient):
                # Log warning ONCE per channel session instead of spamming every second
                if not session.warned_not_voice_recv:
                    logger.warning(
                        f"Voice client in '{voice_channel.name}' is not a VoiceRecvClient ({type(vc).__name__}). "
                        f"Attempting async reconnect with cls=voice_recv.VoiceRecvClient..."
                    )
                    session.warned_not_voice_recv = True

                # Attempt an async reconnect with cls=voice_recv.VoiceRecvClient
                try:
                    logger.info(f"Reconnecting voice client in '{voice_channel.name}' with VoiceRecvClient...")
                    if vc.is_connected():
                        await vc.disconnect(force=True)
                    await asyncio.sleep(0.5)

                    target_client = vc.client if hasattr(vc, "client") else None
                    if not target_client:
                        target_client = (
                            self.orchestrator.clients.get("ttf_vasan")
                            or next(iter(self.orchestrator.clients.values()), None)
                        )
                    guild = target_client.get_guild(voice_channel.guild.id) or voice_channel.guild
                    target_vc = guild.get_channel(voice_channel.id) or voice_channel

                    vc = await target_vc.connect(
                        cls=voice_recv.VoiceRecvClient,
                        reconnect=True,
                        timeout=15.0,
                        self_mute=False,
                        self_deaf=False,
                    )
                except Exception as reconnect_err:
                    logger.warning(
                        f"Reconnecting '{voice_channel.name}' with VoiceRecvClient failed: {reconnect_err}"
                    )
                    vc = None

                # If reconnection fails, degrade gracefully to output-only mode
                if not vc or not isinstance(vc, voice_recv.VoiceRecvClient):
                    session.output_only_mode = True
                    session.is_listening = False
                    logger.info(
                        f"Degraded voice service in '{voice_channel.name}' gracefully to output-only mode "
                        f"(speaking works via FFmpegPCMAudio even without voice_recv)."
                    )
                    return

            # Successfully verified as VoiceRecvClient!
            session.warned_not_voice_recv = False
            session.output_only_mode = False

            def on_voice_packet(user: Optional[discord.User], data: Any):
                # Strictly ignore bot audio packets to avoid feedback loops
                if not user or getattr(user, "bot", False):
                    return

                if not data or not getattr(data, "pcm", None):
                    return

                # Record user audio chunk
                uid = user.id
                session.user_objects[uid] = user
                if uid not in session.user_pcm_buffers:
                    session.user_pcm_buffers[uid] = []

                session.user_pcm_buffers[uid].append(data.pcm)
                session.user_last_packet_time[uid] = time.time()

            try:
                if hasattr(vc, "is_listening") and vc.is_listening():
                    vc.stop_listening()

                sink = voice_recv.BasicSink(on_voice_packet)
                vc.listen(sink)
                session.is_listening = True
                session.listening_voice_client = vc
                logger.info(f"🎙️ Real-time voice listening active in '{voice_channel.name}' via VoiceRecvClient!")
            except Exception as exc:
                logger.error(f"Failed to attach voice sink in '{voice_channel.name}': {exc}")
                session.output_only_mode = True
                session.is_listening = False

        except Exception as exc:
            logger.error(f"Exception in _voice_listener_worker for '{voice_channel.name}': {exc}")
            session.output_only_mode = True
            session.is_listening = False

    def start_listening_in_channel(self, voice_channel: discord.VoiceChannel) -> bool:
        """
        Begins continuous real-time audio reception in the voice channel.
        Attaches BasicSink to capture human speech chunks while ignoring bots.
        """
        if not HAVE_VOICE_RECV or not voice_recv:
            session = self.get_session(voice_channel.id)
            session.output_only_mode = True
            return False

        session = self.get_session(voice_channel.id)
        if session.is_listening:
            return True

        if session.output_only_mode:
            # Degraded gracefully; do not spam worker or warning logs
            return False

        if session.listener_worker_task and not session.listener_worker_task.done():
            return True

        session.listener_worker_task = asyncio.create_task(
            self._voice_listener_worker(voice_channel)
        )
        return True

    def stop_listening_in_channel(self, voice_channel: discord.VoiceChannel):
        """Stops active voice listening in the specified voice channel and resets session flags."""
        session = self.get_session(voice_channel.id)
        session.is_listening = False
        session.output_only_mode = False
        session.warned_not_voice_recv = False

        if session.listener_worker_task and not session.listener_worker_task.done():
            session.listener_worker_task.cancel()
        session.listener_worker_task = None

        vc = session.listening_voice_client
        if vc and hasattr(vc, "is_listening"):
            try:
                if vc.is_listening():
                    vc.stop_listening()
            except Exception:
                pass
        session.listening_voice_client = None
        session.user_pcm_buffers.clear()
        session.user_last_packet_time.clear()
        logger.info(f"Stopped voice listening in '{voice_channel.name}'")

    async def _human_presence_auto_listener_loop(self):
        """
        Periodically verifies all voice channels:
        Automatically starts listening in any VC with human users present,
        and stops listening when humans leave.
        """
        while self.is_running:
            try:
                for client in self.orchestrator.clients.values():
                    if not client.is_ready():
                        continue
                    for guild in client.guilds:
                        for vc in guild.voice_channels:
                            human_users = [m for m in vc.members if not m.bot]
                            session = self.get_session(vc.id)

                            if human_users and not session.is_listening and not session.output_only_mode:
                                self.start_listening_in_channel(vc)
                            elif not human_users and (session.is_listening or session.output_only_mode):
                                self.stop_listening_in_channel(vc)
            except Exception as exc:
                logger.debug(f"Auto-listener tick error: {exc}")

            await asyncio.sleep(12.0)

    def handle_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        """Called on Discord voice_state_update to immediately attach/detach listeners."""
        if member.bot:
            return

        if after.channel:
            session = self.get_session(after.channel.id)
            if not session.output_only_mode:
                self.start_listening_in_channel(after.channel)

        if before.channel and before.channel != after.channel:
            humans_left = [m for m in before.channel.members if not m.bot]
            if not humans_left:
                self.stop_listening_in_channel(before.channel)

    async def _vad_silence_watcher_loop(self):
        """
        High-frequency Voice Activity Detection (VAD) loop:
        Checks if a human user has finished speaking (>= 0.65 seconds of silence after packets).
        When an utterance is complete, immediately triggers Speech Recognition and Gemini reply.
        """
        while self.is_running:
            try:
                now = time.time()
                for ch_id, session in list(self.sessions.items()):
                    if not session.is_listening:
                        continue

                    # If bot is currently speaking, clear buffers to avoid echo
                    if session.is_speaking or session.audio_lock.locked():
                        session.user_pcm_buffers.clear()
                        session.user_last_packet_time.clear()
                        continue

                    for uid, last_time in list(session.user_last_packet_time.items()):
                        # Silence threshold: 0.65 seconds of silence concludes utterance
                        if now - last_time >= 0.65:
                            chunks = session.user_pcm_buffers.pop(uid, [])
                            session.user_last_packet_time.pop(uid, None)

                            if not chunks:
                                continue

                            combined_pcm = b"".join(chunks)
                            # Audio duration check (between 0.4s and 25s)
                            duration_sec = len(combined_pcm) / (48000 * 2 * 2)
                            if 0.4 <= duration_sec <= 25.0:
                                asyncio.create_task(
                                    self._process_completed_user_speech(
                                        session=session,
                                        user_id=uid,
                                        pcm_data=combined_pcm,
                                    )
                                )
            except Exception as exc:
                logger.debug(f"VAD watcher tick error: {exc}")

            await asyncio.sleep(0.10)  # 100ms polling interval for sub-second responsiveness

    async def _process_completed_user_speech(
        self,
        session: VoiceChannelSession,
        user_id: int,
        pcm_data: bytes,
    ):
        """
        Transcribes speech PCM data to text, identifies user intent,
        determines the target bot, and speaks back in under 2 seconds.
        """
        async with session.user_processing_lock:
            # 1. Downsample 48kHz stereo to 16kHz mono PCM
            mono_16k = downsample_pcm_48k_stereo_to_16k_mono(pcm_data)
            if not mono_16k or len(mono_16k) < 3200:
                return

            # 2. Fast Speech Recognition
            audio_data = sr.AudioData(mono_16k, 16000, 2)
            transcript = await self._recognize_speech(audio_data)

            if not transcript or len(transcript.strip()) < 2:
                return

            # Resolve user member
            channel_obj = None
            for client in self.orchestrator.clients.values():
                channel_obj = client.get_channel(session.channel_id)
                if channel_obj:
                    break

            if not isinstance(channel_obj, discord.VoiceChannel):
                return

            cached_user = session.user_objects.get(user_id)
            member = channel_obj.guild.get_member(user_id) or cached_user
            user_display_name = getattr(member, "display_name", None) or getattr(member, "name", "User")

            logger.info(
                f"🎙️ [USER HEARD] {user_display_name} in '{channel_obj.name}': \"{transcript}\""
            )

            # 3. Target Bot Routing: Check if speech addressed a specific bot
            target_bot_key = self._detect_addressed_bot(transcript, channel_obj)

            # 4. Prompt Gemini AI with Character Persona & Conversational Context
            prompt = (
                f"You are {target_bot_key.upper()} in a Discord voice channel.\n"
                f"A team member named {user_display_name} just spoke on the mic and said: \"{transcript}\".\n"
                f"Reply back to them directly in authentic Tanglish (Tamil + English) as your character persona.\n"
                f"Keep it under 15 words, punchy, conversational, and direct so it can be spoken in 2 seconds.\n"
                f"Strictly output only your spoken sentence, no markdown, no quotes, no bot prefixes."
            )

            try:
                response_text = await self.orchestrator.gemini_service.generate_casual_chat(
                    prompt=prompt,
                    character_name=target_bot_key.title(),
                )
            except Exception as exc:
                logger.warning(f"Error generating voice AI reply: {exc}")
                response_text = "All is well nanba, logic clear-ah iruku!"

            clean_response = clean_text_for_speech(response_text)
            if not clean_response:
                clean_response = "Apdiya? Seri paathukalam bro."

            # 5. Continuous Voice Reply in under 2 seconds
            await self.speak_text(
                voice_channel=channel_obj,
                character_key=target_bot_key,
                text=clean_response,
            )

    async def _recognize_speech(self, audio_data: sr.AudioData) -> Optional[str]:
        """
        Performs low-latency asynchronous speech recognition:
        1. Primary: Google Speech Recognition (en-IN - Indian English / Tanglish).
        2. Fallback 1: en-US (standard English).
        3. Fallback 2: ta-IN (Tamil phonetics).
        """
        loop = asyncio.get_running_loop()

        def _recognize_sync():
            for lang in ("en-IN", "en-US", "ta-IN"):
                try:
                    return self.recognizer.recognize_google(audio_data, language=lang)
                except sr.UnknownValueError:
                    continue
                except Exception as exc:
                    logger.debug(f"STT {lang} failed: {exc}")
                    continue
            return None

        try:
            return await asyncio.wait_for(loop.run_in_executor(None, _recognize_sync), timeout=3.5)
        except Exception as exc:
            logger.debug(f"Speech recognition timed out or failed: {exc}")
            return None

    def _detect_addressed_bot(
        self,
        transcript: str,
        voice_channel: discord.VoiceChannel,
    ) -> str:
        """
        Determines which bot should respond based on name invocation keywords in the transcript.
        If no specific bot is mentioned, selects an awake bot currently in the voice channel.
        """
        t = transcript.lower()

        keyword_map = [
            (["vasan", "ttf", "lead"], "ttf_vasan"),
            (["pradeep", "ranganathan", "architect"], "pradeep"),
            (["mamitha", "reenu", "ui", "ux", "design"], "mamitha"),
            (["kayadu", "devops", "backend"], "kayadu"),
            (["muthazhagi", "muthu", "qa", "security"], "muthazhagi"),
            (["vijay", "thalapathy", "vj"], "vijay"),
            (["sivakarthikeyan", "siva", "sk"], "sivakarthikeyan"),
            (["anirudh", "ani", "rockstar", "bgm"], "anirudh"),
            (["trisha", "jessy"], "trisha"),
            (["lokesh", "loki", "director"], "lokesh"),
            (["sadie", "sink"], "sadie"),
            (["millie", "bobby", "brown"], "millie"),
            (["messi", "leo"], "messi"),
            (["ronaldo", "cr7", "siuu"], "ronaldo"),
            (["dhoni", "msd", "thala", "captain"], "dhoni"),
            (["virat", "kohli", "king"], "virat"),
            (["rohit", "hitman", "vadapav"], "rohit"),
            (["jadeja", "jaddu"], "jadeja"),
            (["hardik", "pandya"], "hardik"),
            (["haaland"], "haaland"),
            (["mbappe"], "mbappe"),
            (["neymar"], "neymar"),
        ]

        for keywords, bot_key in keyword_map:
            if any(kw in t for kw in keywords):
                return bot_key

        # If no bot explicitly named: pick an awake bot present in the channel
        present_bots: List[str] = self._get_bots_in_voice_channel(voice_channel)
        if present_bots:
            return random.choice(present_bots)

        # Default fallback: Team Vasan Lead
        return "ttf_vasan"

    # =====================================================================
    # 5. AUDIO BUFFER & AUTO CLEANUP (ZERO STORAGE BLOAT)
    # =====================================================================

    def _safe_remove_file(self, file_path: Optional[str]):
        """Safely deletes a temporary audio file from disk."""
        if not file_path:
            return
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.debug(f"Purged temp voice clip: {os.path.basename(file_path)}")
        except Exception as exc:
            logger.debug(f"Could not purge {file_path}: {exc}")

    async def _auto_purge_loop(self):
        """
        Background janitor loop:
        Scans temp_voice buffer directory every 30 seconds and purges any
        audio files older than 45 seconds to maintain zero storage bloat.
        """
        while self.is_running:
            try:
                now = time.time()
                if os.path.exists(self.temp_dir):
                    for fname in os.listdir(self.temp_dir):
                        if fname.startswith("tts_") or fname.endswith((".mp3", ".wav")):
                            fpath = os.path.join(self.temp_dir, fname)
                            try:
                                mtime = os.path.getmtime(fpath)
                                if now - mtime > 45.0:  # Older than 45 seconds
                                    os.remove(fpath)
                                    logger.debug(f"Auto-purged stale voice buffer: {fname}")
                            except Exception:
                                pass
            except Exception as exc:
                logger.debug(f"Janitor purge tick error: {exc}")

            await asyncio.sleep(30)

    def cleanup_all(self):
        """Shuts down all sessions and purges all temporary files."""
        self.is_running = False
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
        if self._vad_task and not self._vad_task.done():
            self._vad_task.cancel()
        if self._autonomous_conversation_task and not self._autonomous_conversation_task.done():
            self._autonomous_conversation_task.cancel()
        if self._auto_listener_task and not self._auto_listener_task.done():
            self._auto_listener_task.cancel()

        for s in self.sessions.values():
            s.is_listening = False
            if s.listening_voice_client and s.listening_voice_client.is_connected():
                try:
                    asyncio.create_task(s.listening_voice_client.disconnect(force=True))
                except Exception:
                    pass

        # Purge entire temp directory
        try:
            if os.path.exists(self.temp_dir):
                for f in os.listdir(self.temp_dir):
                    try:
                        os.remove(os.path.join(self.temp_dir, f))
                    except Exception:
                        pass
        except Exception:
            pass
        logger.info("Voice engine shut down cleanly. Temp buffer purged.")
