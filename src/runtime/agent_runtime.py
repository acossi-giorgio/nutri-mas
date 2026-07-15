from __future__ import annotations

import asyncio
import atexit
import binascii
from enum import Enum
import hashlib
import logging
import os
from pathlib import Path
from queue import Empty, Queue
import re
import threading
from typing import Any

from dotenv import load_dotenv
from pyjabber import AppConfig
from pyjabber.db.database import DB
from pyjabber.server import Server
from pyjabber.server_parameters import Parameters
from pyjabber.features.SASL.SASL import SASL
from pyjabber.queues.QueueManager import QueueManager, QueueName, get_queue
from pyjabber.queues.workers.MessageQueueWorker import queue_worker
from pyjabber.queues.workers.ServerConnectionWorker import server_connection_worker
import slixmpp

from src.agents.chef_agent import ChefAgent
from src.agents.creative_cook_agent import CreativeCookAgent
from src.agents.gateway_agent import GatewayAgent
from src.agents.nlp_agent import NLPAgent
from src.agents.nutritionist_agent import NutritionistAgent
from src.agents.planner_agent import PlannerAgent
from src.ui.events import EventValidationError, UICommand, UIEvent
from src.utils.ingredient_store import QdrantIngredientStore
from src.utils.llm_config import build_llm_provider
from src.utils.logger import get_logger
from src.utils.time_utils import configure_clock

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_XMPP_SERVER = "localhost"
_PASSWORD = "password"
_USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,63}$")
logger = get_logger("AgentRuntime")


class RuntimeStatus(str, Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    READY = "ready"
    FAILED = "failed"
    CLOSED = "closed"


def configured_username() -> str:
    """Load and validate the only application identity before startup."""
    load_dotenv(_PROJECT_ROOT / "config" / ".env", override=True)
    load_dotenv(_PROJECT_ROOT / ".env", override=False)
    username = (os.getenv("NUTRIMAS_USERNAME") or "").strip().lower()
    if not _USERNAME_RE.fullmatch(username):
        raise RuntimeError(
            "NUTRIMAS_USERNAME must match ^[a-z0-9][a-z0-9_.-]{0,63}$ in config/.env."
        )
    return username


def _clock_speed(value: str | None) -> float:
    """Parse a valid clock speed."""
    try:
        speed = float((value or "1").strip().lower().removesuffix("x"))
    except ValueError:
        return 1.0
    return speed if speed > 0 else 1.0


def _configure_clock() -> None:
    """Configure the shared application clock."""
    speed = _clock_speed(os.getenv("NUTRIMAS_CLOCK_SPEED") or os.getenv("CLOCK_SPEED"))
    configure_clock(
        mode="simulated" if speed != 1 else "real",
        timezone=os.getenv("NUTRIMAS_TIMEZONE") or os.getenv("TIMEZONE"),
        speed=speed,
    )


_slixmpp_initialized = False
_original_slixmpp_init = slixmpp.ClientXMPP.__init__
_original_close_engine = DB.close_engine_async


def install_compatibility_patches() -> None:
    """Install process-wide pyjabber/slixmpp workarounds exactly once."""
    global _slixmpp_initialized
    if _slixmpp_initialized:
        return

    def no_direct_tls(client: Any, *args: object, **kwargs: object) -> None:
        """Disable unsupported direct TLS."""
        _original_slixmpp_init(client, *args, **kwargs)
        client.enable_direct_tls = False

    async def hash_without_process_pool(
        _: object, password: str, salt: bytes, iterations: int
    ) -> str:
        """Hash credentials without a process pool."""
        hashed = await asyncio.to_thread(
            hashlib.pbkdf2_hmac, "sha256", password.encode(), salt, iterations
        )
        return f"sha256${iterations}${binascii.hexlify(salt).decode()}${binascii.hexlify(hashed).decode()}"

    async def close_engine_without_memory_hang() -> None:
        """Close the database engine safely."""
        if getattr(AppConfig.app_config, "database_in_memory", False):
            DB._engine = None
            return
        await _original_close_engine()

    slixmpp.ClientXMPP.__init__ = no_direct_tls
    SASL._hash_scram_async = hash_without_process_pool
    DB.close_engine_async = staticmethod(close_engine_without_memory_hang)
    for name in (
        "agentspeak.runtime",
        "slixmpp",
        "sqlalchemy.pool",
        "litellm",
        "spade",
    ):
        logging.getLogger(name).setLevel(logging.WARNING)
    _slixmpp_initialized = True


class _DisabledServer:
    async def start(self) -> None:
        """Start the embedded XMPP server."""
        await asyncio.Future()


async def _run_pyjabber(server: Server) -> None:
    """Run the embedded XMPP server."""
    _ = get_queue(QueueName.CONNECTIONS)
    _ = get_queue(QueueName.MESSAGES)
    _ = get_queue(QueueName.SERVERS)
    tasks = [
        asyncio.create_task(queue_worker()),
        asyncio.create_task(server_connection_worker()),
        asyncio.create_task(server.run_server()),
    ]
    if getattr(server, "_http_server", None):
        tasks.append(asyncio.create_task(server._http_server.start()))
    try:
        await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


class AgentRuntime:
    """Process-wide runtime shared safely by Streamlit reruns."""

    def __init__(self) -> None:
        """Initialize the instance."""
        self.status = RuntimeStatus.STOPPED
        self.username = ""
        self.accepting_commands = False
        self.command_queue: Queue[str] = Queue()
        self.event_queue: Queue[str] = Queue()
        self._event_history: list[UIEvent] = []
        self._event_history_lock = threading.Lock()
        self.agent_loop: asyncio.AbstractEventLoop | None = None
        self.agent_error = ""
        self.ready_event = threading.Event()
        self.start_lock = threading.Lock()
        self.thread: threading.Thread | None = None
        self._stop_event: asyncio.Event | None = None
        self._shutdown_requested = threading.Event()
        self._agents: dict[str, Any] = {}
        atexit.register(self.close)

    def start(self) -> None:
        """Start all services once; invalid configuration fails before XMPP starts."""
        with self.start_lock:
            if self.status in {RuntimeStatus.STARTING, RuntimeStatus.READY}:
                return
            self.status = RuntimeStatus.STARTING
            self.agent_error = ""
            self.ready_event.clear()
            self._shutdown_requested.clear()
            self.accepting_commands = False
            try:
                self.username = configured_username()
            except RuntimeError as exc:
                self.status = RuntimeStatus.FAILED
                self.agent_error = str(exc)
                self.ready_event.set()
                return
            self.thread = threading.Thread(target=self._thread_main, daemon=True)
            self.thread.start()

    def submit(self, text: str, question_context: str | None = None) -> None:
        """Validate and enqueue user input without touching the asyncio loop."""
        if not self.accepting_commands:
            raise RuntimeError(self.agent_error or "Agent runtime is not ready.")
        self.command_queue.put(
            UICommand(text=text, question_context=question_context).to_json()
        )

    def _collect_pending_events(self) -> list[UIEvent]:
        """Move queued Gateway events into replayable process-wide history."""
        collected: list[UIEvent] = []
        while True:
            try:
                raw = self.event_queue.get_nowait()
            except Empty:
                self._event_history.extend(collected)
                if collected:
                    logger.debug(
                        "Collected %d Gateway event(s); history_size=%d",
                        len(collected),
                        len(self._event_history),
                    )
                return collected
            try:
                collected.append(UIEvent.from_json(raw))
            except EventValidationError as exc:
                collected.append(
                    UIEvent(
                        type="error",
                        message="The agent runtime emitted an invalid UI event.",
                        payload={
                            "code": "invalid_runtime_event",
                            "detail": str(exc),
                            "retryable": True,
                        },
                    )
                )

    def poll_events_since(self, cursor: int) -> tuple[int, list[UIEvent]]:
        """Return events not yet seen by one Streamlit session."""
        with self._event_history_lock:
            self._collect_pending_events()
            history_length = len(self._event_history)
            if cursor < 0 or cursor > history_length:
                cursor = 0
            return history_length, list(self._event_history[cursor:])

    def close(self) -> None:
        """Request shutdown and wait until every agent has flushed its state."""
        if self.status in {RuntimeStatus.CLOSED, RuntimeStatus.STOPPED}:
            return
        self.status = RuntimeStatus.CLOSED
        self.accepting_commands = False
        self._shutdown_requested.set()
        loop = self.agent_loop
        stop_event = self._stop_event
        if loop and stop_event and loop.is_running():
            loop.call_soon_threadsafe(stop_event.set)
        thread = self.thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            timeout = float(os.getenv("AGENT_SHUTDOWN_TIMEOUT_SECONDS", "30"))
            logger.info("Waiting for agent state flush before shutdown...")
            thread.join(timeout=max(0.0, timeout))
            if thread.is_alive():
                logger.error(
                    "Agent shutdown did not complete within %.1f seconds; state may not be persisted.",
                    timeout,
                )
            else:
                logger.info("Agent state flush completed.")

    def _thread_main(self) -> None:
        """Run the agent runtime thread."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.agent_loop = loop
        try:
            loop.run_until_complete(self._run())
        except Exception as exc:
            self.status = RuntimeStatus.FAILED
            self.agent_error = str(exc)
            logger.exception("Agent runtime failed")
        finally:
            self.ready_event.set()
            loop.close()

    async def _run(self) -> None:
        """Run the asynchronous agent lifecycle."""
        install_compatibility_patches()
        _configure_clock()
        QueueManager._queues.clear()
        server = Server(Parameters(host=_XMPP_SERVER, database_in_memory=True))
        if hasattr(server, "_adminServer"):
            server._adminServer = _DisabledServer()
        if hasattr(server, "_http_server"):
            server._http_server = _DisabledServer()
        server_task = asyncio.create_task(_run_pyjabber(server))
        try:
            await asyncio.wait_for(server.ready.wait(), timeout=30)
            await self._start_agents()
            self.status = RuntimeStatus.READY
            self.ready_event.set()
            self._stop_event = asyncio.Event()
            if self._shutdown_requested.is_set():
                self._stop_event.set()
            await self._stop_event.wait()
        finally:
            for agent in self._agents.values():
                try:
                    flush = getattr(agent, "flush_state", None)
                    if flush:
                        flush()
                    await agent.stop()
                except Exception:
                    logger.exception("Agent shutdown failed")
            server_task.cancel()
            await asyncio.gather(server_task, return_exceptions=True)

    async def _start_agents(self) -> None:
        """Create and start all application agents."""
        asl_dir = _PROJECT_ROOT / "src" / "bdi"
        close_handlers: dict[str, Any] = {}
        gateway = GatewayAgent(
            f"gateway@{_XMPP_SERVER}",
            _PASSWORD,
            self.command_queue,
            self.event_queue,
            close_handlers,
        )
        chef = ChefAgent(
            f"chef@{_XMPP_SERVER}", _PASSWORD, asl=str(asl_dir / "chef.asl")
        )
        nutritionist = NutritionistAgent(
            f"nutritionist@{_XMPP_SERVER}",
            _PASSWORD,
            asl=str(asl_dir / "nutritionist.asl"),
            meal_monitor_interval_seconds=30,
        )
        planner = PlannerAgent(
            f"planner@{_XMPP_SERVER}", _PASSWORD, asl=str(asl_dir / "planner.asl")
        )
        for name, agent in (
            ("gateway", gateway),
            ("chef", chef),
            ("nutritionist", nutritionist),
            ("planner", planner),
        ):
            await agent.start()
            self._agents[name] = agent
        close_handlers.update(
            {
                "chef": chef.flush_state,
                "nutritionist": nutritionist.flush_state,
                "planner": planner.flush_state,
            }
        )
        nlp = NLPAgent(f"nlp@{_XMPP_SERVER}", _PASSWORD, build_llm_provider())
        await nlp.start()
        self._agents["nlp"] = nlp
        ingredient_store = QdrantIngredientStore()
        await ingredient_store.build_from_csv(
            str(_PROJECT_ROOT / "src" / "data" / "cook" / "ingredients.csv")
        )
        if not ingredient_store.is_semantic_ready:
            raise RuntimeError("Ingredient semantic store was not fully built.")
        cook = CreativeCookAgent(
            f"cook@{_XMPP_SERVER}",
            _PASSWORD,
            build_llm_provider(),
            ingredient_store=ingredient_store,
        )
        await cook.start()
        self._agents["cook"] = cook
        await gateway.submit_init(self.username)
        self.accepting_commands = True
        gateway.activate_ui()
