import asyncio
import sys
# 1. (必需) 解决 Windows 上的 NotImplementedError
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    print("--- [DEBUG] Event loop policy successfully set to ProactorEventLoopPolicy. ---")

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from settings import PROJECT_ROOT
from src import EverythingAsInterface
from src.core.orchestrator import Orchestrator
from src.core.task_config import TaskConfig
from src.services.webhook_dispatcher import WebhookDispatcher, WebhookJob
from src.services.subscription_registry import SubscriptionRegistry


logger = logging.getLogger("api.server")


API_PREFIX = "/api/v1"

from contextlib import asynccontextmanager
from fastapi import FastAPI
from playwright.async_api import async_playwright, Playwright


# 2. (推荐) 使用 lifespan 管理 Playwright 实例
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize core system
    system = EverythingAsInterface(config_file=os.path.join(PROJECT_ROOT, "config.example.json5"))
    await async_playwright().start()
    # Lazy init orchestrator and scheduler when first task runs
    orchestrator = Orchestrator(browser_config=system.browser_config)
    await orchestrator.start(headless=system.browser_config.headless)
    system.scheduler.set_orchestrator(orchestrator)

    # Initialize webhook components
    dispatcher = WebhookDispatcher()
    await dispatcher.start()
    registry = SubscriptionRegistry()

    app.state.system = system
    app.state.orchestrator = orchestrator
    app.state.dispatcher = dispatcher
    app.state.registry = registry

    logger.info("API server started")

    yield  # 应用在此处运行

    system = app.state.system
    dispatcher: WebhookDispatcher = app.state.dispatcher
    orchestrator: Orchestrator = app.state.orchestrator

    if dispatcher:
        await dispatcher.stop()
    if system and getattr(system, "scheduler", None):
        try:
            await system.scheduler.stop()
        except Exception:
            pass
    if orchestrator:
        try:
            await orchestrator.stop()
        except Exception:
            pass

class CreateTaskBody(BaseModel):
    plugin_id: str
    run_mode: Optional[str] = Field(default="recurring", pattern="^(once|recurring)$")
    interval: Optional[int] = 300
    config: Optional[Dict[str, Any]] = None
    topic_id: Optional[str] = None


class RunPluginBody(BaseModel):
    config: Optional[Dict[str, Any]] = None
    topic_id: Optional[str] = None


class CreateTopicBody(BaseModel):
    name: str
    description: Optional[str] = ""
    topic_id: Optional[str] = None


class CreateSubscriptionBody(BaseModel):
    url: str
    secret: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    enabled: bool = True


def require_api_key(x_api_key: Optional[str] = Header(default=None)) -> None:
    expected = os.getenv("EAI_API_KEY", "testkey")
    if expected:
        if not x_api_key or x_api_key != expected:
            raise HTTPException(status_code=401, detail="Unauthorized")
    # if not configured, open access (dev mode)


def build_event_envelope(*, topic_id: str, plugin_id: Optional[str], task_id: Optional[str], result: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "event_id": str(uuid.uuid4()),
        "topic_id": topic_id,
        "plugin_id": plugin_id,
        "task_id": task_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": {
            "environment": os.getenv("EAI_ENV", "development"),
        },
        "result": result,
    }


def create_app() -> FastAPI:
    app = FastAPI(title="Everything As An Interface - Server", version="1.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # State holders
    app.state.system = None
    app.state.orchestrator = None
    app.state.dispatcher = None
    app.state.registry = None
    app.state._bridged_topics = set()

    # Health
    @app.get(f"{API_PREFIX}/health")
    async def health() -> Dict[str, str]:
        return {"status": "ok"}

    @app.get(f"{API_PREFIX}/ready")
    async def ready() -> Dict[str, Any]:
        ok = app.state.system is not None and app.state.orchestrator is not None
        return {"ready": bool(ok)}

    async def _ensure_bridge(topic_id: str) -> None:
        system: EverythingAsInterface = app.state.system
        if topic_id in app.state._bridged_topics:
            return
        async def _bridge(data: Dict[str, Any]) -> None:
            envelope = build_event_envelope(
                topic_id=topic_id,
                plugin_id=data.get("plugin_id"),
                task_id=data.get("task_id"),
                result=data,
            )
            await _dispatch_topic(topic_id, envelope)
        system.subscription_system.subscribe(topic_id, _bridge)
        app.state._bridged_topics.add(topic_id)

    # Plugins
    @app.get(f"{API_PREFIX}/plugins", dependencies=[Depends(require_api_key)])
    async def list_plugins() -> Dict[str, Any]:
        system: EverythingAsInterface = app.state.system
        return {"plugins": system.plugin_manager.list_available_plugins()}

    # Tasks
    @app.get(f"{API_PREFIX}/tasks", dependencies=[Depends(require_api_key)])
    async def list_tasks() -> Dict[str, Any]:
        system: EverythingAsInterface = app.state.system
        return {"tasks": system.scheduler.get_all_tasks()}

    @app.post(f"{API_PREFIX}/tasks", dependencies=[Depends(require_api_key)])
    async def create_task(body: CreateTaskBody) -> Dict[str, Any]:
        system: EverythingAsInterface = app.state.system
        config = TaskConfig.from_dict(body.config or {})

        topic_id = body.topic_id
        system.scheduler.set_orchestrator(app.state.orchestrator)
        if not system.scheduler.running:
            await system.scheduler.start()

        # Ensure topic bridge if provided
        if topic_id:
            await _ensure_bridge(topic_id)

        async def _task_callback(result: Dict[str, Any]) -> None:
            if topic_id:
                # enrich with minimal identity for downstream
                enriched = dict(result)
                enriched.setdefault("plugin_id", body.plugin_id)
                enriched.setdefault("task_id", task_id)
                envelope = build_event_envelope(
                    topic_id=topic_id,
                    plugin_id=body.plugin_id,
                    task_id=task_id,
                    result=enriched,
                )
                await _dispatch_topic(topic_id, envelope)

        # Handle run_mode once by setting a very large interval after first run trigger
        interval = int(body.interval or 300)
        if (body.run_mode or "recurring") == "once":
            interval = 10**9

        task_id = system.scheduler.add_task(
            plugin_id=body.plugin_id,
            interval=interval,
            callback=_task_callback if topic_id else None,
            config=config,
        )

        return {"task_id": task_id}

    @app.post(f"{API_PREFIX}/plugins/{{plugin_id}}/run", dependencies=[Depends(require_api_key)])
    async def run_plugin(plugin_id: str, body: RunPluginBody) -> Dict[str, Any]:
        system: EverythingAsInterface = app.state.system
        orchestrator: Orchestrator = app.state.orchestrator
        config = TaskConfig.from_dict(body.config or {})

        # Prepare cookies
        cookie_ids = config.get("cookie_ids") or []
        cookie_items = None
        if system.account_manager and cookie_ids:
            valid = []
            for cid in cookie_ids:
                ok, _ = system.account_manager.check_cookie_validity(cid)
                if ok:
                    valid.append(cid)
            if valid:
                cookie_items = system.account_manager.merge_cookies(valid)

        ctx = await orchestrator.allocate_context_page(
            cookie_items=cookie_items,
            account_manager=system.account_manager,
            settings={"plugin": plugin_id, "ephemeral": True},
        )
        plugin = system.plugin_manager.instantiate_plugin(plugin_id, ctx, config)
        await plugin.start()
        try:
            result = await plugin.fetch()
        finally:
            await plugin.stop()

        if body.topic_id:
            await _ensure_bridge(body.topic_id)
            envelope = build_event_envelope(
                topic_id=body.topic_id,
                plugin_id=plugin_id,
                task_id=None,
                result=result,
            )
            await _dispatch_topic(body.topic_id, envelope)

        return {"success": True, "result": result}

    # Topics & Subscriptions (webhook)
    @app.get(f"{API_PREFIX}/topics", dependencies=[Depends(require_api_key)])
    async def get_topics() -> Dict[str, Any]:
        system: EverythingAsInterface = app.state.system
        return {"topics": system.subscription_system.get_all_topics()}

    @app.post(f"{API_PREFIX}/topics", dependencies=[Depends(require_api_key)])
    async def create_topic(body: CreateTopicBody) -> Dict[str, Any]:
        system: EverythingAsInterface = app.state.system
        registry: SubscriptionRegistry = app.state.registry
        topic_id = system.subscription_system.create_topic(body.name, body.description or "", topic_id=body.topic_id)
        registry.ensure_topic(topic_id, body.name, body.description or "")
        await _ensure_bridge(topic_id)
        return {"topic_id": topic_id}

    @app.post(f"{API_PREFIX}/topics/{{topic_id}}/subscriptions", dependencies=[Depends(require_api_key)])
    async def create_subscription(topic_id: str, body: CreateSubscriptionBody) -> Dict[str, Any]:
        system: EverythingAsInterface = app.state.system
        registry: SubscriptionRegistry = app.state.registry
        if not system.subscription_system.get_topic(topic_id):
            raise HTTPException(status_code=404, detail="Topic not found")
        sub_id = registry.add_subscription(topic_id, body.url, secret=body.secret, headers=body.headers or {})
        return {"subscription_id": sub_id}

    @app.delete(f"{API_PREFIX}/subscriptions/{{subscription_id}}", dependencies=[Depends(require_api_key)])
    async def delete_subscription(subscription_id: str) -> Dict[str, Any]:
        registry: SubscriptionRegistry = app.state.registry
        ok = registry.remove_subscription(subscription_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Subscription not found")
        return {"deleted": True}

    @app.patch(f"{API_PREFIX}/subscriptions/{{subscription_id}}", dependencies=[Depends(require_api_key)])
    async def patch_subscription(subscription_id: str, enabled: Optional[bool] = None) -> Dict[str, Any]:
        registry: SubscriptionRegistry = app.state.registry
        if enabled is None:
            raise HTTPException(status_code=400, detail="Missing 'enabled' query param")
        ok = registry.enable_subscription(subscription_id, enabled=bool(enabled))
        if not ok:
            raise HTTPException(status_code=404, detail="Subscription not found")
        return {"updated": True}

    @app.post(f"{API_PREFIX}/subscriptions/test-delivery", dependencies=[Depends(require_api_key)])
    async def test_delivery(topic_id: str) -> Dict[str, Any]:
        if not app.state.system.subscription_system.get_topic(topic_id):
            raise HTTPException(status_code=404, detail="Topic not found")
        await _ensure_bridge(topic_id)
        envelope = build_event_envelope(
            topic_id=topic_id,
            plugin_id=None,
            task_id=None,
            result={"success": True, "message": "test"},
        )
        await _dispatch_topic(topic_id, envelope)
        return {"enqueued": True, "event_id": envelope["event_id"]}

    @app.get(f"{API_PREFIX}/tasks/{{task_id}}", dependencies=[Depends(require_api_key)])
    async def get_task(task_id: str) -> Dict[str, Any]:
        system: EverythingAsInterface = app.state.system
        task = system.scheduler.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        return {"task": task.to_dict()}

    @app.delete(f"{API_PREFIX}/tasks/{{task_id}}", dependencies=[Depends(require_api_key)])
    async def delete_task(task_id: str) -> Dict[str, Any]:
        system: EverythingAsInterface = app.state.system
        ok = system.scheduler.remove_task(task_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Task not found")
        return {"deleted": True}

    @app.post(f"{API_PREFIX}/topics/{{topic_id}}/publish", dependencies=[Depends(require_api_key)])
    async def manual_publish(topic_id: str) -> Dict[str, Any]:
        if not app.state.system.subscription_system.get_topic(topic_id):
            raise HTTPException(status_code=404, detail="Topic not found")
        await _ensure_bridge(topic_id)
        envelope = build_event_envelope(
            topic_id=topic_id,
            plugin_id=None,
            task_id=None,
            result={"success": True, "manual": True},
        )
        await _dispatch_topic(topic_id, envelope)
        return {"enqueued": True, "event_id": envelope["event_id"]}

    @app.get(f"{API_PREFIX}/subscriptions", dependencies=[Depends(require_api_key)])
    async def list_subscriptions(topic_id: Optional[str] = None) -> Dict[str, Any]:
        registry: SubscriptionRegistry = app.state.registry
        return {"subscriptions": registry.list_subscriptions(topic_id)}

    @app.get(f"{API_PREFIX}/dead-letters", dependencies=[Depends(require_api_key)])
    async def dead_letters() -> Dict[str, Any]:
        dispatcher: WebhookDispatcher = app.state.dispatcher
        return {"dead_letters": dispatcher.get_dead_letters()}

    async def _dispatch_topic(topic_id: str, envelope: Dict[str, Any]) -> None:
        registry: SubscriptionRegistry = app.state.registry
        dispatcher: WebhookDispatcher = app.state.dispatcher
        subs = registry.get_active_subscriptions_for_topic(topic_id)
        for s in subs:
            job = WebhookJob(
                event_id=envelope["event_id"],
                topic_id=topic_id,
                plugin_id=envelope.get("plugin_id"),
                payload=envelope,
                url=s["url"],
                secret=s.get("secret"),
                headers=s.get("headers") or {},
            )
            await dispatcher.enqueue(job)

    return app


app = create_app()

