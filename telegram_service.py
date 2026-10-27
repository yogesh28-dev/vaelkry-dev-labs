"""
Vaelkry Dev Labs - Multi-Agent Enterprise Discord System
Telegram Autonomous Telemetry & Alert Service
Provides startup notifications, runtime error telemetry, and CEO executive dispatches.
"""

import os
import sys
import logging
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
import aiohttp
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("VaelkryDevLabs.Telegram")

class TelegramAlertService:
    """
    Autonomous alert and telemetry service connecting Vaelkry Dev Labs
    directly to the Executive Telegram Channel / CEO Smartphone.
    """

    API_BASE = "https://api.telegram.org/bot"

    def __init__(
        self,
        bot_token: Optional[str] = None,
        default_chat_id: Optional[str | int] = None,
    ):
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.default_chat_id = default_chat_id or os.getenv("TELEGRAM_CHAT_ID") or os.getenv("TELEGRAM_CEO_CHAT_ID")
        self._session: Optional[aiohttp.ClientSession] = None
        self._cached_chat_id: Optional[str | int] = self.default_chat_id

        if not self.bot_token:
            logger.warning("TELEGRAM_BOT_TOKEN not configured. Telegram alerts disabled.")
        else:
            logger.info("TelegramAlertService initialized.")

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10)
            )
        return self._session

    async def close(self):
        """Closes the underlying aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def discover_chat_id(self) -> Optional[str | int]:
        """
        Queries Telegram getUpdates to automatically discover the most recent
        chat ID that messaged the bot if no chat ID is defined in .env.
        """
        if self._cached_chat_id:
            return self._cached_chat_id

        if not self.bot_token:
            return None

        url = f"{self.API_BASE}{self.bot_token}/getUpdates"
        try:
            session = await self._get_session()
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    result = data.get("result", [])
                    if result:
                        # Grab the most recent message's chat id
                        for update in reversed(result):
                            msg = update.get("message") or update.get("channel_post") or update.get("my_chat_member")
                            if msg and "chat" in msg:
                                cid = msg["chat"]["id"]
                                self._cached_chat_id = cid
                                logger.info(f"Auto-discovered Telegram chat ID: {cid}")
                                return cid
        except Exception as exc:
            logger.debug(f"Could not auto-discover Telegram chat ID: {exc}")

        return None

    async def send_message(
        self,
        text: str,
        chat_id: Optional[str | int] = None,
        parse_mode: str = "HTML",
        disable_web_page_preview: bool = True,
    ) -> bool:
        """
        Asynchronously sends a message via Telegram Bot API with automatic chunking.
        """
        if not self.bot_token:
            logger.warning("Skipping Telegram dispatch: No bot token configured.")
            return False

        target_chat = chat_id or self._cached_chat_id
        if not target_chat:
            target_chat = await self.discover_chat_id()

        if not target_chat:
            logger.warning(
                "Skipping Telegram dispatch: No chat ID configured or discovered. "
                "Set TELEGRAM_CHAT_ID in .env or message your bot on Telegram."
            )
            return False

        url = f"{self.API_BASE}{self.bot_token}/sendMessage"
        session = await self._get_session()

        # Telegram message length limit is 4096 characters
        chunks = [text[i : i + 4000] for i in range(0, len(text), 4000)]
        success = True

        for chunk in chunks:
            payload = {
                "chat_id": target_chat,
                "text": chunk,
                "parse_mode": parse_mode,
                "disable_web_page_preview": disable_web_page_preview,
            }
            try:
                async with session.post(url, json=payload) as resp:
                    if resp.status == 200:
                        logger.info(f"Telegram telemetry dispatch delivered to {target_chat}.")
                    else:
                        resp_data = await resp.text()
                        logger.error(f"Telegram API error ({resp.status}): {resp_data}")
                        # Fallback retry without HTML formatting if tag mismatch occurs
                        if parse_mode == "HTML" and "can't parse entities" in resp_data.lower():
                            payload["parse_mode"] = ""
                            async with session.post(url, json=payload) as retry_resp:
                                if retry_resp.status != 200:
                                    success = False
                        else:
                            success = False
            except Exception as exc:
                logger.error(f"Failed to transmit Telegram message: {exc}")
                success = False

        return success

    async def send_startup_alert(
        self,
        bot_count: int,
        active_squads: List[str],
        guild_name: str = "Vaelkry Dev Labs",
        guild_id: Optional[int] = None,
    ) -> bool:
        """
        Dispatches executive startup telemetry to Telegram upon multi-agent system activation.
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S IST")
        squads_formatted = ", ".join(s.replace("_", " ").title() for s in active_squads)

        text = (
            "🚀 <b>VAELKRY DEV LABS | AUTONOMOUS SYSTEM ONLINE</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⚡ <b>Status:</b> Production Ready & Synchronized\n"
            f"🤖 <b>Connected Nodes:</b> <code>{bot_count}/32 Agents Active</code>\n"
            f"🏢 <b>Corporate Guild:</b> <code>{guild_name}</code> (ID: <code>{guild_id or 'N/A'}</code>)\n"
            f"👥 <b>Active Squads:</b> {squads_formatted}\n"
            f"👑 <b>Executive Leads:</b> Sadie Sink (CEO) & Millie Bobby Brown (COO)\n"
            f"🕒 <b>Boot Timestamp:</b> <code>{now}</code>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "<i>Multi-agent autonomous cycle, voice synthesis, and telemetry monitoring enabled.</i>"
        )
        return await self.send_message(text)

    async def send_error_telemetry(
        self,
        error_type: str,
        message: str,
        agent_name: Optional[str] = None,
        traceback_str: Optional[str] = None,
    ) -> bool:
        """
        Transmits real-time system failure telemetry to the engineering team on Telegram.
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S IST")
        safe_msg = message.replace("<", "&lt;").replace(">", "&gt;")[:600]
        agent_label = agent_name or "System Core"

        text = (
            "⚠️ <b>VAELKRY DEV LABS | TELEMETRY INCIDENT REPORT</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔴 <b>Error Type:</b> <code>{error_type}</code>\n"
            f"👤 <b>Origin Agent / Service:</b> <code>{agent_label}</code>\n"
            f"🕒 <b>Timestamp:</b> <code>{now}</code>\n"
            f"📝 <b>Message:</b>\n<code>{safe_msg}</code>\n"
        )

        if traceback_str:
            safe_tb = traceback_str.replace("<", "&lt;").replace(">", "&gt;")[-1000:]
            text += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n<b>Stack Trace:</b>\n<pre>{safe_tb}</pre>\n"

        text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n<i>Autonomous fail-safe mechanisms engaged.</i>"
        return await self.send_message(text)

    async def send_ceo_alert(
        self,
        title: str,
        description: str,
        priority: str = "HIGH",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Dispatches an executive briefing alert straight to Sadie Sink (CEO).
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S IST")
        safe_title = title.replace("<", "&lt;").replace(">", "&gt;")
        safe_desc = description.replace("<", "&lt;").replace(">", "&gt;")

        priority_emoji = "🔴" if priority.upper() == "CRITICAL" else "🟡" if priority.upper() == "HIGH" else "🔵"

        text = (
            f"👑 <b>VAELKRY DEV LABS | CEO EXECUTIVE DIRECTIVE</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{priority_emoji} <b>Priority Level:</b> <code>{priority.upper()}</code>\n"
            f"📌 <b>Directive / Alert:</b> <b>{safe_title}</b>\n"
            f"🕒 <b>Logged:</b> <code>{now}</code>\n\n"
            f"<b>Details:</b>\n{safe_desc}\n"
        )

        if metadata:
            text += "\n<b>Telemetry Metadata:</b>\n"
            for k, v in metadata.items():
                text += f"• <b>{k}:</b> <code>{v}</code>\n"

        text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n<i>Sent via Vaelkry Autonomous Executive Dispatcher.</i>"
        return await self.send_message(text)

    async def send_test_dispatch(self, user_name: str = "Executive Admin") -> Tuple[bool, str]:
        """
        Sends an immediate verification test dispatch for the /telemetry_test slash command.
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S IST")

        # Ensure we have target chat ID
        chat_id = self._cached_chat_id or await self.discover_chat_id()
        if not self.bot_token:
            return False, "TELEGRAM_BOT_TOKEN is missing in .env!"

        if not chat_id:
            return (
                False,
                "No Telegram Chat ID found! Send any message (e.g. '/start') to your Telegram bot "
                "first, or set TELEGRAM_CHAT_ID in .env, then rerun /telemetry_test.",
            )

        text = (
            "🛰️ <b>VAELKRY DEV LABS | TELEMETRY TEST DISPATCH</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"✅ <b>Status:</b> Connection Established\n"
            f"👤 <b>Triggered By:</b> <code>{user_name}</code>\n"
            f"📡 <b>Target Chat ID:</b> <code>{chat_id}</code>\n"
            f"🕒 <b>Timestamp:</b> <code>{now}</code>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "<i>Autonomous telemetry bridge between Discord and Telegram is 100% operational! ⚡</i>"
        )

        ok = await self.send_message(text, chat_id=chat_id)
        if ok:
            return True, f"Telemetry dispatch delivered successfully to Telegram chat `{chat_id}`!"
        else:
            return False, f"Failed to deliver Telegram dispatch. Check logs for API details."
