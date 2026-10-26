"""
Vaelkry Dev Labs - Bidirectional Real-Time AI Voice Engine
Orchestrates:
1. Per-Character Neural TTS Voice Mapping (Edge-TTS / Azure) with custom pitch, rate, and tone.
2. VC Dialogue Engine for spontaneous cross-bot banter with realistic 1.5-3.0s turn-taking audio locks.
3. Bidirectional Real-Time Human Speech Recognition & Sub-2-Second Contextual Voice Reply (discord-ext-voice-recv + SpeechRecognition + Gemini).
4. Zero-Bloat Audio Buffer & Auto Cleanup.
"""

import asyncio
import io
import logging
import os
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
)

logger = logging.getLogger("VaelkryDevLabs.VoiceEngine")


def clean_text_for_speech(text: str) -> str:
    """
    Cleans raw bot output or user messages for clear, natural Edge-TTS speech synthesis.
    Strips Discord mentions, channel IDs, markdown symbols, URLs, and Unicode emojis.
    """
    if not text:
        return ""

    # 1. Remove Discord mentions <@...>, <#...>, <@&...>, emojis <:name:id>
    t = re.sub(r"<[@#&]!?[0-9]+>", "", text)
    t = re.sub(r"<a?:[a-zA-Z0-9_]+:[0-9]+>", "", t)

    # 2. Extract markdown link text [Text](url) -> Text
    t = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", t)

    # 3. Strip URLs
    t = re.sub(r"https?://\S+", "", t)

    # 4. Strip markdown formatting: *, _, ~, `, #, >, |
    t = re.sub(r"[*_~`#>|]", "", t)

    # 5. Remove bot speaker prefixes like "[Vijay]:", "Vijay:", "**Sadie**:"
    t = re.sub(r"^(?:\[.*?\]|\*\*.*?\*\*|[A-Za-z0-9_]+)\s*:\s*", "", t)

    # 6. Remove quotes at the boundaries
    t = t.strip()
    if (t.startswith('"') and t.endswith('"')) or (t.startswith("'") and t.endswith("'")):
        t = t[1:-1].strip()

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
    - Listening state and incoming user audio buffers.
    """

    def __init__(self, channel_id: int):
        self.channel_id = channel_id
        self.audio_lock = asyncio.Lock()
        self.is_speaking = False
        self.current_speaker: Optional[str] = None
        self.last_speech_finished_at: float = 0.0
        self.is_listening = False
        self.voice_client: Optional[discord.VoiceClient] = None
        self.user_pcm_buffers: Dict[int, List[bytes]] = {}
        self.user_last_packet_time: Dict[int, float] = {}
        self.user_processing_lock = asyncio.Lock()


class VoiceService:
    """
    Bidirectional Real-Time AI Voice Engine for Vaelkry Dev Labs:
    1. Edge-TTS Synthesis with per-character neural voice mapping (pitch & speed).
    2. VC Dialogue Engine with sequential turn-taking and natural pauses.
    3. Real-time human speech recognition & contextual sub-2s voice replies.
    4. Zero-bloat audio buffering and automatic instant cleanup.
    """

    def __init__(self, orchestrator: Any):
        self.orchestrator = orchestrator
        self.sessions: Dict[int, VoiceChannelSession] = {}
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 280
        self.recognizer.dynamic_energy_threshold = True

        # Resolve FFmpeg executable safely
        try:
            self.ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            self.ffmpeg_exe = "ffmpeg"

        # Dedicated temporary audio buffer directory
        self.temp_dir = os.path.join(tempfile.gettempdir(), "vaelkry_voice_buffer")
        os.makedirs(self.temp_dir, exist_ok=True)

        self._cleanup_task: Optional[asyncio.Task] = None
        self._vad_task: Optional[asyncio.Task] = None
        self.is_running = True

        # Start background watchdog & janitor tasks
        self._start_background_tasks()

    def _start_background_tasks(self):
        """Initializes background audio auto-cleanup and speech VAD listeners."""
        loop = asyncio.get_event_loop()
        if not self._cleanup_task or self._cleanup_task.done():
            self._cleanup_task = loop.create_task(self._auto_purge_loop())
        if not self._vad_task or self._vad_task.done():
            self._vad_task = loop.create_task(self._vad_silence_watcher_loop())

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

        profile = self.get_character_voice_profile(character_key)
        voice_name = profile["voice"]
        pitch = profile.get("pitch", "+0Hz")
        rate = profile.get("rate", "+0%")

        filename = f"tts_{character_key}_{uuid.uuid4().hex[:10]}.mp3"
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
                    f"TTS Synthesized for {character_key} ({voice_name}, pitch={pitch}, rate={rate}): "
                    f"'{clean_text[:50]}...' -> {os.path.basename(file_path)} ({os.path.getsize(file_path)} bytes)"
                )
                return file_path
            else:
                logger.error(f"TTS file was empty or missing for {character_key}: {file_path}")
                return None
        except Exception as exc:
            logger.exception(f"Edge-TTS synthesis error for {character_key} with voice {voice_name}: {exc}")
            # Fallback attempt with default en-US voice if specialized regional voice fails
            try:
                fallback_comm = edge_tts.Communicate(text=clean_text, voice="en-US-GuyNeural")
                await fallback_comm.save(file_path)
                return file_path
            except Exception as fb_exc:
                logger.error(f"Fallback TTS failed as well: {fb_exc}")
                return None

    # =====================================================================
    # 2. AUDIO PLAYBACK & SEQUENTIAL TURN-TAKING ENGINE
    # =====================================================================

    async def get_or_connect_voice_client(
        self,
        voice_channel: discord.VoiceChannel,
        preferred_bot_key: Optional[str] = None,
    ) -> Optional[discord.VoiceClient]:
        """
        Finds or establishes a connected VoiceClient inside the target voice channel.
        Prioritizes the preferred bot's client so their avatar illuminates green in Discord.
        Seamlessly uses discord-ext-voice-recv VoiceRecvClient when available.
        """
        session = self.get_session(voice_channel.id)

        # 1. Check if preferred bot has an active voice connection here
        if preferred_bot_key and preferred_bot_key in self.orchestrator.clients:
            client = self.orchestrator.clients[preferred_bot_key]
            vc = discord.utils.get(client.voice_clients, channel=voice_channel)
            if vc and vc.is_connected():
                session.voice_client = vc
                return vc

        # 2. Check if any connected bot client is already inside this channel
        for client in self.orchestrator.clients.values():
            vc = discord.utils.get(client.voice_clients, channel=voice_channel)
            if vc and vc.is_connected():
                session.voice_client = vc
                return vc

        # 3. If none connected, connect using preferred bot or lead bot
        connector_client = None
        if preferred_bot_key and preferred_bot_key in self.orchestrator.clients:
            connector_client = self.orchestrator.clients[preferred_bot_key]
        if not connector_client:
            connector_client = (
                self.orchestrator.clients.get("ttf_vasan")
                or self.orchestrator.clients.get("vijay")
                or next(iter(self.orchestrator.clients.values()), None)
            )

        if not connector_client:
            logger.error("No bot clients available to connect to voice channel.")
            return None

        try:
            # Check existing connection for this client elsewhere
            existing_vc = discord.utils.get(connector_client.voice_clients, guild=voice_channel.guild)
            if existing_vc and existing_vc.is_connected():
                if existing_vc.channel.id != voice_channel.id:
                    await existing_vc.move_to(voice_channel)
                session.voice_client = existing_vc
                return existing_vc

            # Connect fresh with VoiceRecvClient for bidirectional audio
            connect_cls = voice_recv.VoiceRecvClient if HAVE_VOICE_RECV else discord.VoiceClient
            vc = await voice_channel.connect(cls=connect_cls, reconnect=True, timeout=15.0)
            session.voice_client = vc
            logger.info(
                f"Connected {connector_client.user.name if connector_client.user else 'bot'} to VC '{voice_channel.name}'"
            )
            return vc
        except Exception as exc:
            logger.error(f"Failed to connect bot to voice channel {voice_channel.name}: {exc}")
            return None

    async def play_audio_file(
        self,
        voice_client: discord.VoiceClient,
        audio_path: str,
    ) -> bool:
        """
        Streams PCM audio into Discord via FFmpegPCMAudio.
        Asynchronously waits until playback completes.
        Purges the temporary audio file immediately upon playback conclusion.
        """
        if not voice_client or not voice_client.is_connected():
            logger.warning("Voice client is not connected; cannot play audio.")
            self._safe_remove_file(audio_path)
            return False

        loop = asyncio.get_event_loop()
        done_event = asyncio.Event()

        def _after_playback(error):
            if error:
                logger.warning(f"Audio playback completed with error: {error}")
            loop.call_soon_threadsafe(done_event.set)
            # Automatic instant cleanup (Requirement 4)
            self._safe_remove_file(audio_path)

        try:
            # If already playing, stop current stream cleanly
            if voice_client.is_playing():
                voice_client.stop()

            source = discord.FFmpegPCMAudio(
                audio_path,
                executable=self.ffmpeg_exe,
                options="-filter:a volume=1.15",
            )
            voice_client.play(source, after=_after_playback)
            # Wait for playback to conclude cleanly
            await done_event.wait()
            return True
        except Exception as exc:
            logger.exception(f"Error during audio stream playback: {exc}")
            self._safe_remove_file(audio_path)
            return False

    async def speak_text(
        self,
        voice_channel: discord.VoiceChannel,
        character_key: str,
        text: str,
        caller_client: Optional[discord.Client] = None,
    ) -> bool:
        """
        Synthesizes and speaks text over the voice channel stream.
        Guarantees strict turn-taking using the channel's audio lock so bots never talk over each other.
        """
        session = self.get_session(voice_channel.id)

        # Acquire per-channel audio lock for turn-taking (Requirement 2)
        async with session.audio_lock:
            session.is_speaking = True
            session.current_speaker = character_key

            audio_file = await self.synthesize_speech(text, character_key)
            if not audio_file:
                session.is_speaking = False
                session.current_speaker = None
                return False

            # Obtain active VoiceClient in this VC
            vc = await self.get_or_connect_voice_client(voice_channel, preferred_bot_key=character_key)
            if not vc:
                self._safe_remove_file(audio_file)
                session.is_speaking = False
                session.current_speaker = None
                return False

            logger.info(
                f"🔊 [{character_key.upper()}] Speaking in '{voice_channel.name}': \"{text}\""
            )

            success = await self.play_audio_file(vc, audio_file)
            session.is_speaking = False
            session.current_speaker = None
            session.last_speech_finished_at = time.time()
            return success

    # =====================================================================
    # 3. VC DIALOGUE ENGINE (SPONTANEOUS CROSS-BOT SPEECH & BANTER)
    # =====================================================================

    async def trigger_cross_bot_banter(
        self,
        voice_channel: discord.VoiceChannel,
        bot_a_key: str,
        bot_b_key: str,
        topic: Optional[str] = None,
        initial_line: Optional[str] = None,
    ):
        """
        Executes spontaneous cross-bot speech banter in a voice channel:
        1. Bot A speaks its line over the voice channel.
        2. Waits 1.5 - 3.0 seconds (natural turn-taking human pause).
        3. Bot B generates a contextual witty retort via Gemini AI and speaks back.
        Turn-taking queue lock ensures zero overlap.
        """
        session = self.get_session(voice_channel.id)

        # Resolve initial dialogue line
        if not initial_line:
            info_a = CASUAL_PLAYER_CHARACTERS.get(CHARACTER_VOICE_ALIASES.get(bot_a_key, bot_a_key), {})
            sample = info_a.get("sample", "All is well nanba, calm-ah execute pannuvom.")
            initial_line = sample

        logger.info(
            f"Initiating cross-bot voice banter in '{voice_channel.name}' between {bot_a_key} and {bot_b_key}"
        )

        # --- Turn 1: Bot A Speaks ---
        await self.speak_text(voice_channel, bot_a_key, initial_line)

        # --- Inter-Turn Pause: 1.5 to 3.0 seconds (Requirement 2) ---
        pause_duration = 1.5 + (0.5 * (time.time() % 3))
        logger.debug(f"Turn-taking pause of {pause_duration:.2f}s before {bot_b_key} responds...")
        await asyncio.sleep(pause_duration)

        # --- Turn 2: Bot B Generates and Speaks Reply ---
        prompt = build_voice_banter_prompt(
            bot_a_key=bot_a_key,
            bot_b_key=bot_b_key,
            topic=topic,
            previous_utterance=initial_line,
        )

        reply_text = ""
        try:
            raw_reply = await self.orchestrator.gemini_service.generate_casual_chat(
                prompt=prompt,
                character_name=bot_b_key.title(),
            )
            reply_text = clean_text_for_speech(raw_reply)
        except Exception as exc:
            logger.warning(f"Error generating banter reply for {bot_b_key}: {exc}")

        if not reply_text:
            info_b = CASUAL_PLAYER_CHARACTERS.get(CHARACTER_VOICE_ALIASES.get(bot_b_key, bot_b_key), {})
            fallbacks = info_b.get("fallback_samples", ["Un alapparai ku alave illama pochu da!"])
            reply_text = fallbacks[0]

        await self.speak_text(voice_channel, bot_b_key, reply_text)

    async def run_autonomous_vc_banter_if_populated(
        self,
        voice_channel: discord.VoiceChannel,
    ):
        """
        Checks members inside a voice channel (e.g. Tech Cafe or Sleep Room).
        If multiple bots or users are present, organically triggers a crisp 2-turn banter exchange.
        """
        session = self.get_session(voice_channel.id)
        if session.is_speaking or session.audio_lock.locked():
            return

        # Find which bots from our orchestrator are inside this voice channel
        bots_in_vc: List[str] = []
        for k, client in self.orchestrator.clients.items():
            if client.user:
                member = voice_channel.guild.get_member(client.user.id)
                if member and member.voice and member.voice.channel and member.voice.channel.id == voice_channel.id:
                    bots_in_vc.append(k)

        if len(bots_in_vc) >= 2:
            import random
            bot_a, bot_b = random.sample(bots_in_vc, 2)
            asyncio.create_task(
                self.trigger_cross_bot_banter(
                    voice_channel=voice_channel,
                    bot_a_key=bot_a,
                    bot_b_key=bot_b,
                )
            )

    # =====================================================================
    # 4. REAL-TIME HUMAN SPEECH RECOGNITION & CONTEXTUAL VOICE REPLY
    # =====================================================================

    def start_listening_in_channel(self, voice_channel: discord.VoiceChannel) -> bool:
        """
        Begins continuous real-time audio reception in the voice channel.
        Attaches the UserVoiceSink to capture human speech chunks.
        """
        if not HAVE_VOICE_RECV:
            logger.warning(
                "discord-ext-voice-recv is not installed; voice receiving disabled."
            )
            return False

        session = self.get_session(voice_channel.id)
        if session.is_listening:
            logger.info(f"Already listening in VC '{voice_channel.name}'")
            return True

        # Ensure VoiceRecvClient is connected
        loop = asyncio.get_event_loop()

        async def _attach_sink():
            vc = await self.get_or_connect_voice_client(voice_channel)
            if not vc or not isinstance(vc, voice_recv.VoiceRecvClient):
                logger.warning(f"Voice client in {voice_channel.name} is not a VoiceRecvClient.")
                return

            def on_voice_packet(user: Optional[discord.User], data: Any):
                if not user or getattr(user, "bot", False):
                    return  # Strictly ignore bot audio packets

                if not data or not data.pcm:
                    return

                # Record packet into user buffer
                uid = user.id
                if uid not in session.user_pcm_buffers:
                    session.user_pcm_buffers[uid] = []

                session.user_pcm_buffers[uid].append(data.pcm)
                session.user_last_packet_time[uid] = time.time()

            try:
                sink = voice_recv.BasicSink(on_voice_packet)
                vc.listen(sink)
                session.is_listening = True
                logger.info(f"🎙️ Real-time voice listening active in '{voice_channel.name}'!")
            except Exception as exc:
                logger.error(f"Failed to start voice listening: {exc}")

        asyncio.create_task(_attach_sink())
        return True

    def stop_listening_in_channel(self, voice_channel: discord.VoiceChannel):
        """Stops active voice listening in the specified voice channel."""
        session = self.get_session(voice_channel.id)
        session.is_listening = False
        if session.voice_client and hasattr(session.voice_client, "is_listening"):
            try:
                if session.voice_client.is_listening():
                    session.voice_client.stop_listening()
            except Exception:
                pass
        session.user_pcm_buffers.clear()
        session.user_last_packet_time.clear()
        logger.info(f"Stopped voice listening in '{voice_channel.name}'")

    async def _vad_silence_watcher_loop(self):
        """
        High-frequency Voice Activity Detection (VAD) loop:
        Checks if a human user has finished speaking (>= 0.75 seconds of silence after packets).
        When an utterance is complete, immediately triggers Speech Recognition and Gemini reply.
        """
        while self.is_running:
            try:
                now = time.time()
                for ch_id, session in list(self.sessions.items()):
                    if not session.is_listening or session.is_speaking:
                        continue

                    for uid, last_time in list(session.user_last_packet_time.items()):
                        # Silence threshold: 0.75 seconds of silence concludes utterance
                        if now - last_time >= 0.75:
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

            await asyncio.sleep(0.12)  # 120ms polling interval for sub-second responsiveness

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

            # 2. Fast Speech Recognition (Google Speech endpoint with Indian English & Tamil support)
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

            member = channel_obj.guild.get_member(user_id)
            user_display_name = member.display_name if member else "User"

            logger.info(
                f"🎙️ [USER HEARD] {user_display_name} in '{channel_obj.name}': \"{transcript}\""
            )

            # 3. Target Bot Routing: Check if speech addressed a specific bot
            target_bot_key = self._detect_addressed_bot(transcript, channel_obj)

            # 4. Prompt Gemini AI with Character Persona & Conversational Context
            prompt = build_voice_reply_prompt(
                character_key=target_bot_key,
                user_name=user_display_name,
                user_speech=transcript,
                channel_name=channel_obj.name,
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
        loop = asyncio.get_event_loop()

        def _recognize_sync():
            # Try Indian English / Tanglish first
            try:
                return self.recognizer.recognize_google(audio_data, language="en-IN")
            except sr.UnknownValueError:
                pass
            except Exception as exc:
                logger.debug(f"STT en-IN error: {exc}")

            # Try en-US
            try:
                return self.recognizer.recognize_google(audio_data, language="en-US")
            except sr.UnknownValueError:
                pass
            except Exception:
                pass

            # Try ta-IN
            try:
                return self.recognizer.recognize_google(audio_data, language="ta-IN")
            except Exception:
                pass

            return None

        try:
            return await loop.run_in_executor(None, _recognize_sync)
        except Exception as exc:
            logger.warning(f"Speech recognition execution failed: {exc}")
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
        present_bots: List[str] = []
        for k, client in self.orchestrator.clients.items():
            if client.user:
                m = voice_channel.guild.get_member(client.user.id)
                if m and m.voice and m.voice.channel and m.voice.channel.id == voice_channel.id:
                    present_bots.append(k)

        if present_bots:
            import random
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

        for s in self.sessions.values():
            s.is_listening = False
            if s.voice_client and s.voice_client.is_connected():
                try:
                    asyncio.create_task(s.voice_client.disconnect(force=True))
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
