"""
Vaelkry Dev Labs - Multi-Agent Enterprise Discord System
Supabase Database Service & Long-Term Memory Storage
Handles persistent agent memory, corporate project tasks, and squad XP leveling.
Includes seamless local JSON fallback for zero-downtime offline resilience.
"""

import os
import sys
import json
import logging
import asyncio
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

try:
    from supabase import create_client, Client
except ImportError:
    create_client = None
    Client = None

logger = logging.getLogger("VaelkryDevLabs.Database")

FALLBACK_STORE_FILE = "agent_data_store.json"

class DatabaseService:
    """
    Manages long-term agent memory, project task persistence, and squad XP rankings.
    Uses Supabase cloud database with resilient local caching when offline.
    """

    def __init__(
        self,
        supabase_url: Optional[str] = None,
        supabase_key: Optional[str] = None,
    ):
        self.supabase_url = (
            supabase_url
            or os.getenv("SUPABASE_URL")
            or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
        )
        self.supabase_key = (
            supabase_key
            or os.getenv("SUPABASE_SECRET_KEY")
            or os.getenv("SUPABASE_PUBLISHABLE_KEY")
            or os.getenv("SUPABASE_KEY")
        )

        self.client: Optional[Client] = None
        self.is_connected = False
        self._fallback_path = os.path.join(os.path.dirname(__file__), FALLBACK_STORE_FILE)
        self._local_lock = asyncio.Lock()
        self._init_local_store()

        if create_client and self.supabase_url and self.supabase_key:
            try:
                self.client = create_client(self.supabase_url, self.supabase_key)
                self.is_connected = True
                logger.info(f"Supabase client connected successfully to {self.supabase_url}.")
            except Exception as exc:
                logger.warning(
                    f"Could not initialize live Supabase connection: {exc}. "
                    "Operating with resilient local fallback storage."
                )
                self.client = None
                self.is_connected = False
        else:
            logger.info(
                "Supabase URL or Key not set or incomplete in environment. "
                "Active in Resilient Local Storage mode."
            )

    def _init_local_store(self):
        """Initializes local JSON store if it does not already exist."""
        if not os.path.exists(self._fallback_path):
            default_data = {
                "memories": [],
                "tasks": [],
                "squad_xp": {
                    "team_vasan": {"xp": 1250, "level": 4, "tasks_completed": 12},
                    "team_vijay": {"xp": 1100, "level": 3, "tasks_completed": 10},
                    "team_messi": {"xp": 950, "level": 3, "tasks_completed": 8},
                    "team_dhoni": {"xp": 1020, "level": 3, "tasks_completed": 9},
                    "team_elon": {"xp": 1300, "level": 4, "tasks_completed": 14},
                    "team_tony": {"xp": 1450, "level": 4, "tasks_completed": 15},
                },
                "xp_logs": [],
            }
            try:
                with open(self._fallback_path, "w", encoding="utf-8") as f:
                    json.dump(default_data, f, indent=2)
            except Exception as exc:
                logger.error(f"Error creating fallback data store: {exc}")

    def _read_local_store(self) -> Dict[str, Any]:
        try:
            with open(self._fallback_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"memories": [], "tasks": [], "squad_xp": {}, "xp_logs": []}

    def _write_local_store(self, data: Dict[str, Any]):
        try:
            with open(self._fallback_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as exc:
            logger.error(f"Error saving to fallback data store: {exc}")

    # ==================== 1. LONG-TERM AGENT MEMORY ====================

    async def store_agent_memory(
        self,
        agent_name: str,
        squad: str,
        memory_type: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Stores an episodic or semantic memory entry for an autonomous agent.
        """
        record = {
            "id": str(uuid.uuid4()),
            "agent_name": agent_name,
            "squad": squad,
            "memory_type": memory_type,  # e.g., 'dialogue', 'architecture', 'decision', 'reflection'
            "content": content,
            "metadata": metadata or {},
            "created_at": datetime.now().isoformat(),
        }

        if self.is_connected and self.client:
            try:
                resp = await asyncio.to_thread(
                    lambda: self.client.table("agent_memories").insert(record).execute()
                )
                if resp and resp.data:
                    logger.debug(f"Saved memory for {agent_name} in Supabase cloud.")
                    return resp.data[0]
            except Exception as exc:
                logger.warning(f"Supabase store_agent_memory failed: {exc}. Storing locally.")

        async with self._local_lock:
            data = self._read_local_store()
            data.setdefault("memories", []).append(record)
            self._write_local_store(data)

        return record

    async def get_recent_memories(
        self,
        agent_name: Optional[str] = None,
        squad: Optional[str] = None,
        memory_type: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Retrieves recent long-term memories filtered by agent, squad, or type.
        """
        if self.is_connected and self.client:
            try:
                query = self.client.table("agent_memories").select("*")
                if agent_name:
                    query = query.eq("agent_name", agent_name)
                if squad:
                    query = query.eq("squad", squad)
                if memory_type:
                    query = query.eq("memory_type", memory_type)
                resp = await asyncio.to_thread(
                    lambda: query.order("created_at", desc=True).limit(limit).execute()
                )
                if resp and resp.data:
                    return resp.data
            except Exception as exc:
                logger.warning(f"Supabase get_recent_memories failed: {exc}. Reading locally.")

        async with self._local_lock:
            data = self._read_local_store()
            memories = data.get("memories", [])
            filtered = memories
            if agent_name:
                filtered = [m for m in filtered if m.get("agent_name", "").lower() == agent_name.lower()]
            if squad:
                filtered = [m for m in filtered if m.get("squad", "").lower() == squad.lower()]
            if memory_type:
                filtered = [m for m in filtered if m.get("memory_type", "").lower() == memory_type.lower()]

            return sorted(filtered, key=lambda x: x.get("created_at", ""), reverse=True)[:limit]

    # ==================== 2. CORPORATE PROJECT TASKS ====================

    async def create_project_task(
        self,
        title: str,
        squad: str,
        assigned_to: str,
        description: str,
        priority: str = "HIGH",
        status: str = "PENDING",
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Creates and persists an engineering task assigned to a squad or agent.
        """
        task_record = {
            "id": f"TASK-{str(uuid.uuid4())[:8].upper()}",
            "title": title,
            "squad": squad,
            "assigned_to": assigned_to,
            "description": description,
            "priority": priority,
            "status": status,
            "tags": tags or [],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

        if self.is_connected and self.client:
            try:
                resp = await asyncio.to_thread(
                    lambda: self.client.table("project_tasks").insert(task_record).execute()
                )
                if resp and resp.data:
                    logger.info(f"Task {task_record['id']} saved to Supabase.")
                    return resp.data[0]
            except Exception as exc:
                logger.warning(f"Supabase create_project_task failed: {exc}. Storing locally.")

        async with self._local_lock:
            data = self._read_local_store()
            data.setdefault("tasks", []).append(task_record)
            self._write_local_store(data)

        return task_record

    async def update_task_status(
        self,
        task_id: str,
        status: str,
        result_summary: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Updates task lifecycle status (PENDING, IN_PROGRESS, REVIEW, COMPLETED).
        """
        updates = {
            "status": status,
            "updated_at": datetime.now().isoformat(),
        }
        if result_summary:
            updates["result_summary"] = result_summary

        if self.is_connected and self.client:
            try:
                resp = await asyncio.to_thread(
                    lambda: self.client.table("project_tasks").update(updates).eq("id", task_id).execute()
                )
                if resp and resp.data:
                    return resp.data[0]
            except Exception as exc:
                logger.warning(f"Supabase update_task_status failed: {exc}. Updating locally.")

        async with self._local_lock:
            data = self._read_local_store()
            tasks = data.get("tasks", [])
            for t in tasks:
                if t.get("id") == task_id:
                    t.update(updates)
                    self._write_local_store(data)
                    return t

        return None

    async def get_squad_tasks(
        self,
        squad: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Retrieves project tasks for a given squad or status.
        """
        if self.is_connected and self.client:
            try:
                query = self.client.table("project_tasks").select("*")
                if squad:
                    query = query.eq("squad", squad)
                if status:
                    query = query.eq("status", status)
                resp = await asyncio.to_thread(
                    lambda: query.order("created_at", desc=True).limit(limit).execute()
                )
                if resp and resp.data:
                    return resp.data
            except Exception as exc:
                logger.warning(f"Supabase get_squad_tasks failed: {exc}. Fetching locally.")

        async with self._local_lock:
            data = self._read_local_store()
            tasks = data.get("tasks", [])
            filtered = tasks
            if squad:
                filtered = [t for t in filtered if t.get("squad", "").lower() == squad.lower()]
            if status:
                filtered = [t for t in filtered if t.get("status", "").upper() == status.upper()]
            return sorted(filtered, key=lambda x: x.get("created_at", ""), reverse=True)[:limit]

    # ==================== 3. SQUAD XP & GAMIFICATION ====================

    async def add_squad_xp(
        self,
        squad: str,
        xp_amount: int,
        reason: str,
        agent_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Awards XP to a squad, calculating level progression and logging achievements.
        """
        norm_squad = squad.lower().strip()
        log_entry = {
            "id": str(uuid.uuid4()),
            "squad": norm_squad,
            "xp_added": xp_amount,
            "reason": reason,
            "agent_name": agent_name or "System",
            "timestamp": datetime.now().isoformat(),
        }

        async with self._local_lock:
            data = self._read_local_store()
            squad_map = data.setdefault("squad_xp", {})
            curr = squad_map.setdefault(
                norm_squad,
                {"xp": 0, "level": 1, "tasks_completed": 0},
            )
            curr["xp"] += xp_amount
            if "complete" in reason.lower() or "deliver" in reason.lower():
                curr["tasks_completed"] = curr.get("tasks_completed", 0) + 1

            # Level formula: level = floor(sqrt(xp / 80)) + 1
            curr["level"] = int((curr["xp"] / 80) ** 0.5) + 1
            data.setdefault("xp_logs", []).append(log_entry)
            self._write_local_store(data)

            stats = {
                "squad": norm_squad,
                "xp": curr["xp"],
                "level": curr["level"],
                "tasks_completed": curr["tasks_completed"],
                "gained": xp_amount,
                "reason": reason,
            }

        # Also push to Supabase if available
        if self.is_connected and self.client:
            try:
                await asyncio.to_thread(
                    lambda: self.client.table("squad_xp_logs").insert(log_entry).execute()
                )
                await asyncio.to_thread(
                    lambda: self.client.table("squad_stats").upsert({
                        "squad": norm_squad,
                        "xp": stats["xp"],
                        "level": stats["level"],
                        "tasks_completed": stats["tasks_completed"],
                        "updated_at": datetime.now().isoformat(),
                    }).execute()
                )
            except Exception as exc:
                logger.debug(f"Supabase squad stats upsert exception: {exc}")

        return stats

    async def get_squad_stats(self, squad: str) -> Dict[str, Any]:
        """
        Returns stats and rank for an engineering squad.
        """
        norm_squad = squad.lower().strip()
        leaderboard = await self.get_leaderboard()
        for idx, entry in enumerate(leaderboard):
            if entry.get("squad", "").lower() == norm_squad:
                entry["rank"] = idx + 1
                return entry

        return {"squad": norm_squad, "xp": 0, "level": 1, "tasks_completed": 0, "rank": len(leaderboard) + 1}

    async def get_leaderboard(self) -> List[Dict[str, Any]]:
        """
        Returns all squads ranked by total accumulated XP.
        """
        async with self._local_lock:
            data = self._read_local_store()
            squad_map = data.get("squad_xp", {})
            board = []
            for s_name, stats in squad_map.items():
                board.append({
                    "squad": s_name,
                    "name": s_name.replace("_", " ").title(),
                    "xp": stats.get("xp", 0),
                    "level": stats.get("level", 1),
                    "tasks_completed": stats.get("tasks_completed", 0),
                })

        return sorted(board, key=lambda x: x["xp"], reverse=True)

    # ==================== 4. HEALTH & TELEMETRY ====================

    async def health_check(self) -> Dict[str, Any]:
        """
        Returns database health and aggregate memory/task statistics.
        """
        async with self._local_lock:
            data = self._read_local_store()
            mem_count = len(data.get("memories", []))
            task_count = len(data.get("tasks", []))

        return {
            "connected_to_cloud": self.is_connected,
            "backend": "Supabase Cloud" if self.is_connected else "Local Resilient Store",
            "total_memories": mem_count,
            "total_tasks": task_count,
            "fallback_store": self._fallback_path,
        }
