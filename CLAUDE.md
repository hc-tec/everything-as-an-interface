# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Everything As An Interface (万物皆接口)** is a Python-based automation framework that converts websites and applications into programmable interfaces. It enables automated data collection, monitoring, and aggregation from platforms like Xiaohongshu (小红书), Bilibili, Zhihu, and AI chat services.

The system exposes a FastAPI server that allows RPC clients to trigger plugins for data collection, with support for webhooks, subscriptions, and scheduled tasks.

## Development Commands

### Running the Server

```bash
# Start the FastAPI server (binds to 127.0.0.1:8008)
python run.py

# The server runs without hot-reload by default (hot-reload breaks browser automation)
```

### Testing

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_filename.py

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test markers
pytest -m unit          # Unit tests only
pytest -m integration   # Integration tests only
pytest -m "not slow"    # Exclude slow tests
```

### Code Quality

```bash
# Format code with ruff
ruff format .

# Lint code
ruff check .

# Auto-fix linting issues
ruff check --fix .

# Type checking with mypy
mypy src/

# Format with black (alternative)
black src/

# Sort imports with isort
isort src/
```

### Installation

```bash
# Install dependencies
pip install -r requirements-dev.txt
pip install -r requirements-rpc.txt

# Install Playwright browsers
playwright install
```

## Architecture

The codebase follows a layered architecture designed for extensibility and reusability:

### Layer Hierarchy (Bottom to Top)

1. **Infrastructure Layer** (`src/utils/`, browser automation)
   - Playwright-based browser automation
   - Storage backends (MongoDB/SQLite - MongoDB not fully tested)
   - Configuration management via `config.example.json5`

2. **Tools & Configuration Layer** (`src/config/`, `src/utils/`)
   - **ConfigFactory**: Centralized config loading from `config.example.json5`
   - **Helper Classes**: LoginHelper, ScrollHelper for cross-plugin reusable capabilities
   - Helper design philosophy: functional decoupling, single responsibility, testability

3. **Data Sync Layer** (`src/data_sync/`)
   - **PassiveSyncEngine**: Incremental sync with fingerprint-based change detection
   - Detects additions, updates, and (planned) deletions by comparing batches to local snapshots
   - Stop conditions: consecutive known items, no-change batches, max new items

4. **Service Layer** (`src/services/`)
   - Reusable domain logic for data collection (e.g., note collection, search, video details)
   - Services are platform-specific but shared across multiple plugin entry points
   - Base class: `BaseService` with delegate pattern for lifecycle hooks
   - Key services:
     - `NetCollectionService`: Network-driven collection loop
     - `ScrollHelper`: Scroll-based pagination
     - Platform-specific services in `src/services/{platform}/`

5. **Plugin System Layer** (`src/plugins/`, `src/core/plugin_manager.py`)
   - **BasePlugin**: Abstract base class for all plugins with lifecycle methods
   - Plugin lifecycle: `__init__` → `set_params` → `start` → `fetch` → `stop`
   - Plugins orchestrate services and handle page navigation/entry points
   - Registry-based plugin discovery via decorators
   - Plugin manager auto-discovers plugins from `src/plugins/` on startup

6. **Core Business Layer** (`src/core/`)
   - **Orchestrator**: Manages browser contexts and plugin execution
   - **Scheduler**: Task scheduling and recurring job management
   - **SubscriptionSystem**: Topic/subscription management for webhooks
   - **AccountManager**: Cookie encryption/decryption using master_key
   - **CaptchaCenter**: Captcha handling (future enhancement)

7. **External Interface Layer** (`src/api/`)
   - **FastAPI Server** (`src/api/server.py`): REST API for plugin invocation
   - **WebhookDispatcher**: Asynchronous webhook delivery with retry/dead-letter queue
   - **RPC Client** (`client_sdk/`): Python SDK for consuming the API

### Key Design Patterns

- **Plugin Registry Pattern**: Plugins self-register via decorators
- **Service Delegate Pattern**: Services expose lifecycle hooks for custom behavior
- **Passive Sync Pattern**: Data sync engine compares batches without active crawling
- **Helper Extraction**: Common capabilities (login, scroll) extracted from BasePlugin

## Important Configuration

### config.example.json5

- `app.master_key`: Symmetric encryption key for cookie storage (keep secure!)
- `browser.headless`: Set to `false` for manual login, `true` for automation
- `browser.channel`: Browser to use (e.g., "msedge", "chrome")
- `plugins.enabled_plugins`: Use `["*"]` to enable all, or list specific plugin IDs
- `plugins.auto_discover`: Set to `true` to recursively discover plugins in `src/plugins/`

### Environment Variables

- `EAI_API_KEY`: API key for server authentication (defaults to "testkey")
- Configuration is primarily managed via `config.example.json5`, not environment variables

## Plugin Development

### Creating a New Plugin

1. Create a new file in `src/plugins/{platform}/{plugin_name}.py`
2. Inherit from `BasePlugin` and define required class attributes:
   - `PLUGIN_ID`: Unique identifier
   - `PLUGIN_NAME`: Human-readable name
   - `PLUGIN_DESCRIPTION`: Brief description
3. Implement the `fetch()` method (required abstract method)
4. Register the plugin using the `@register_plugin` decorator
5. Use existing services from `src/services/{platform}/` when possible

### Plugin Parameters

Plugins accept three parameter types:
- **TaskParams**: Browser/task configuration (headless, cookies, viewport)
- **ServiceParams**: Service-level config (max_items, scroll settings, timeouts)
- **SyncParams**: Data sync behavior (stop conditions, fingerprint settings)

See `client_sdk/params.py` for full parameter definitions.

### Login Flow

- Plugins use `LoginHelper` (created automatically in `set_context`)
- Cookie-based login is attempted first via `_try_cookie_login()`
- Manual login fallback via `_manual_login()` if cookies fail
- Override `_is_logged_in()` for platform-specific login detection
- Cookies are encrypted and stored in `accounts/cookies.enc`

## Data Collection Patterns

### Network-Driven Collection

Use `NetCollectionService` for API-based data collection:
1. Set up network listeners via `NetRuleBus`
2. Trigger page actions (scroll, navigation)
3. Service captures responses and parses data
4. PassiveSyncEngine handles incremental sync

### DOM-Based Collection

Use `ScrollHelper` for scraping rendered page elements:
1. Define element selectors
2. Configure scroll behavior (pause, idle rounds)
3. Extract data from DOM nodes
4. Apply sync logic

## Code Style Guidelines (from Cursor rules)

- Follow PEP 8 style guide
- **Use type hints extensively** - prefer creating typed dataclasses over `Dict[str, Any]`
- Write docstrings for functions and classes
- Use descriptive variable/function/class names
- Implement robust error handling and logging with context capture
- Prefer list comprehensions when appropriate
- Limit global variables to reduce side effects

## Testing Strategy

- Unit tests for individual components (mark with `@pytest.mark.unit`)
- Integration tests for plugin workflows (mark with `@pytest.mark.integration`)
- Slow tests should be marked with `@pytest.mark.slow`
- Playwright-based tests should use `pytest-playwright`
- Mock external services and network calls in unit tests

## Client SDK Usage

RPC clients connect to the server and invoke plugins:

```python
from client_sdk.rpc_client_async import EAIRPCClient
from client_sdk.params import TaskParams, ServiceParams

client = EAIRPCClient(
    base_url="http://127.0.0.1:8008",
    api_key="testkey"
)
await client.start()

# Call plugin methods directly
result = await client.
{plugin_method}(
    task_params=TaskParams(cookie_ids=["uuid"]),
    service_params=ServiceParams(max_items=100)
)

await client.stop()
```

## Troubleshooting

### Server Issues

- Check health endpoint: `http://127.0.0.1:8008/api/v1/health`
- Verify API key matches `EAI_API_KEY` environment variable
- Check logs in `logs/app.log` (rotated, max 10MB per file)

### Cookie Issues

- Cookie IDs are logged after successful login
- Cookies expire - re-run manual login flow
- Check `accounts/cookies.enc` exists and is readable

### Browser Automation Issues

- Disable hot-reload (`reload=False` in `run.py`)
- Use `headless=False` for debugging
- Check Playwright browser installation: `playwright install`
- On Windows, event loop policy is set to `ProactorEventLoopPolicy`

## Project Structure Notes

- `src/plugins/`: Plugin entry points (orchestration and page navigation)
- `src/services/`: Reusable collection logic (shared across plugins)
- `src/core/`: System-level components (scheduler, orchestrator, plugin manager)
- `src/data_sync/`: Incremental sync engine and storage abstraction
- `src/utils/`: Cross-cutting utilities (browser, login, scrolling, metrics)
- `client_sdk/`: Python SDK for external consumption
- `data/`: Local data storage (JSON files)
- `accounts/`: Encrypted cookie storage

## Common Gotchas

- Hot-reload breaks Playwright browser launch - always use `reload=False`
- Cookie encryption requires `master_key` in config - don't commit production keys
- PassiveSyncEngine deletion policy is not fully implemented yet
- MongoDB support is present but not fully tested - SQLite is recommended
- Network collection relies on response interception - ensure proper NetRule setup
- Plugin must be enabled in config to be instantiated by plugin manager
