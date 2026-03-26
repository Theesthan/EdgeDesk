# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

EdgeDesk is a local, privacy-first AI desktop automation agent. Read this fully before writing any code. Every rule here is non-negotiable.

---

## Project Identity

**EdgeDesk** is a local, privacy-first AI desktop automation agent for Windows/Linux. It uses on-device LLMs (via Ollama), LangChain ReAct agents, and GUI automation libraries to execute natural-language instructions across desktop applications.

**Core constraint:** Zero external API calls in production. All LLM inference runs through the local Ollama HTTP server (localhost:11434).

**Stack summary:** Python 3.12 · PyQt6 · LangChain 0.3 · Ollama · PyAutoGUI · SQLAlchemy · Pydantic v2 · APScheduler · FAISS · sentence-transformers

---

## Architecture Map

```text
main.py → SystemTrayApp (ui/tray.py)
        → OverlayWindow (ui/overlay.py)   [Alt+Space hotkey]
        → AgentOrchestrator (core/agent.py)
              → OllamaLLM (core/llm.py)
              → ToolManifest (tools/*.py)
              → AgentMemory (core/memory.py → SQLite)
        → SchedulerEngine (scheduler/engine.py)
        → DBSession (db/models.py → SQLite via SQLAlchemy)
        → VectorStore (db/vector_store.py → FAISS)
```

Key paths:

- `core/` — LLM, agent logic, memory, planning

- `tools/` — Screen OCR, GUI control, files, email, clipboard, notifications

- `scheduler/` — APScheduler cron/file/manual triggers

- `db/` — SQLAlchemy models, CRUD, FAISS vector store

- `ui/` — PyQt6 tray, overlay, panels, design system

- `schemas/` — Pydantic v2 I/O models for all agent tools

- `tests/` — pytest test suite

---

## Commands

```bash
# Setup (run before each session)
uv sync

# Run the app
uv run python main.py

# Run all tests
uv run pytest tests/ -v

# Run a single test file
uv run pytest tests/test_agent.py -v

# Run a single test by name
uv run pytest tests/test_agent.py::test_function_name -v

# Run async tests (pytest-asyncio required)
uv run pytest tests/ -v --asyncio-mode=auto

# Lint (check only)
uv run ruff check .

# Format + auto-fix lint
uv run ruff format . && uv run ruff check . --fix

# Type check
uv run mypy . --ignore-missing-imports

# Build single executable
uv run pyinstaller main.py --onefile --windowed --name edgedesk
```

---

## Coding Standards (ALWAYS follow)

### Python Style

- Python 3.12+ features only: use `match/case`, `X | Y` union types, `TypeAlias`, PEP 695 generics where appropriate

- All functions/methods must have full type annotations including return types

- Use `from __future__ import annotations` at top of every file

- Prefer dataclasses or Pydantic models over raw dicts for structured data

- `async/await` for all LLM calls and I/O operations — use `asyncio` throughout

- No bare `except:` — always catch specific exceptions

- Use `loguru` for all logging — never `print()` in production code

- Constants in `SCREAMING_SNAKE_CASE` at module top

- Max line length: 100 characters

- Use `pathlib.Path` everywhere — never `os.path` string joins

### File Organization

- Max 300 lines per file — split into sub-modules if larger

- One class per file (exceptions: small helper dataclasses alongside their user)

- Import order: stdlib → third-party → local (enforced by ruff)

- All public functions/classes need docstrings (Google style)

### Pydantic Schemas (schemas/models.py)

- Every agent tool input AND output MUST have a Pydantic v2 model

- Use `model_validator` for cross-field validation

- Never pass raw dicts to agent tools — always use typed schemas

### Error Handling

- All GUI automation calls wrapped in try/except with retry logic (max 3 retries, exponential backoff)

- Agent tool errors must return a structured `ToolError` Pydantic model, not raise exceptions to the agent

- Log every error with `loguru` including context (tool name, input args, screen state)

---

## LangChain Agent Rules

- Use `create_react_agent` with a custom system prompt — do NOT use deprecated `initialize_agent`

- Tool descriptions must be < 100 chars and action-verb first (e.g. "Click a UI element at screen coordinates")

- Agent system prompt must include: current date/time, available tools list, privacy reminder (no external calls)

- Use `ConversationSummaryBufferMemory` with `max_token_limit=2000` backed by SQLite

- Every LangChain tool must inherit from `BaseTool` and have `args_schema` set to a Pydantic model

- Stream LLM output to UI using `AsyncIteratorCallbackHandler`

- Model selection logic: if VRAM > 8GB → `mistral-nemo:12b`, else → `phi3.5:3.8b`

---

## UI / Design System (CRITICAL — Read Fully)

EdgeDesk UI must look like a **premium native desktop application** — NOT generic AI chat UI, NOT Bootstrap defaults, NOT MUI out-of-the-box. The aesthetic is: **dark glassmorphism meets macOS Raycast meets Linear app**.

### Design Tokens (use these constants — defined in ui/styles/theme.py)

```python
# Color Palette
BG_PRIMARY    = "#0a0a0f"    # Near-black, slightly blue-tinted
BG_SURFACE    = "#12121a"    # Card/panel background
BG_ELEVATED   = "#1a1a26"    # Elevated surfaces, dropdowns
GLASS_BG      = "rgba(255,255,255,0.04)"   # Frosted glass base
GLASS_BORDER  = "rgba(255,255,255,0.08)"   # Subtle borders

ACCENT_PRIMARY  = "#7c6af7"   # Purple-indigo — main brand color
ACCENT_GLOW     = "rgba(124,106,247,0.3)"  # Glow effect base
ACCENT_SUCCESS  = "#22c55e"   # Green
ACCENT_WARNING  = "#f59e0b"   # Amber
ACCENT_ERROR    = "#ef4444"   # Red

TEXT_PRIMARY    = "#f0f0f8"   # Near-white with slight blue
TEXT_SECONDARY  = "#8888aa"   # Muted, dimmer labels
TEXT_TERTIARY   = "#444466"   # Disabled, placeholder

RADIUS_SM  = 6
RADIUS_MD  = 10
RADIUS_LG  = 16
RADIUS_XL  = 22

SHADOW_CARD  = "0 4px 24px rgba(0,0,0,0.5)"
SHADOW_GLOW  = "0 0 20px rgba(124,106,247,0.25)"
```

### Typography

- Font stack: `"Inter"` → `"Segoe UI"` → `system-ui`

- Download Inter from Google Fonts and bundle it in `ui/assets/fonts/`

- Sizes: Title=18px/semibold, Body=13px/regular, Caption=11px/medium, Code=12px/JetBrains Mono

- Line heights: 1.5 for body, 1.2 for headings, 1.8 for dense info

### The Overlay (ui/overlay.py) — most important component

- Frameless window, `Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint`

- Blur background: use `QGraphicsBlurEffect` or Windows DWM ACRYLIC via ctypes

- Width: 680px, centered on screen

- Rounded corners: 22px

- Input field: full-width, 48px tall, no border, transparent bg, placeholder "Ask EdgeDesk anything..."

- Input has animated bottom-border on focus (accent color, 2px, smooth CSS transition)

- Step log: scrollable area below input, each step shown as a pill with icon + text + status dot

- Step pill colors: pending=TEXT_TERTIARY, running=ACCENT_PRIMARY (animated pulse), done=ACCENT_SUCCESS, failed=ACCENT_ERROR

- Animate overlay in: scale from 0.95 + fade in opacity, 180ms ease-out

- Dismiss on Esc or click-outside

### Visual Rules — DO NOT VIOLATE

1. **No white backgrounds anywhere** — the entire app is dark-only

2. **No solid-color flat cards** — all cards use `GLASS_BG` with `GLASS_BORDER` and backdrop blur

3. **No default PyQt6 styling** — every widget must have custom QSS applied

4. **Consistent border radius** — use the token constants, never ad-hoc values

5. **Subtle micro-animations** — hover states (100ms), button press feedback, status transitions

6. **No harsh full-opacity lines** — all separators/borders use the semi-transparent `GLASS_BORDER`

7. **Iconography:** use `qtawesome` (Font Awesome 6 icons) — no emoji, no text-only buttons

8. **Spacing grid:** all margins/padding in multiples of 4px — never odd values like 7px or 13px

9. **Minimum contrast:** TEXT_SECONDARY on BG_SURFACE must meet WCAG AA (4.5:1) — verify in code

10. **Status indicators:** always combine color + icon + text — never color alone

### Rule Manager Panel

- Left sidebar: list of rules as cards (name, trigger type badge, enabled toggle, run count)

- Rule card hover: subtle BG_ELEVATED transition, left-border accent line appears

- Right panel: rule detail editor — triggered by card click, slides in from right (200ms)

- Enabled toggle: custom PyQt6 toggle switch — NOT default QCheckBox

### History View

- Timeline layout — each entry is a row with: timestamp, rule name chip, status dot, duration, feedback buttons

- Group by date (sticky date headers)

- Expand row on click to show full step log

- Thumbs up/down buttons on each row (icon only, small, no label)

### Settings Dialog

- Modal, 640×480px

- Tab navigation: General · LLM · Hotkeys · Privacy

- Smooth tab indicator (animated sliding underline, ACCENT_PRIMARY color)

---

## 21st.dev Magic MCP — UI Component Design

The `magic` MCP server (`@21st-dev/magic`) is available in this session. **Use it before building any new PyQt6 widget or panel.** It generates polished React component designs whose visual specs translate directly into PyQt6 QSS.

### When to invoke

Call `mcp__magic__21st_magic_component_builder` before implementing any of these:

- The command overlay (`ui/overlay.py`) — spotlight/Raycast-style input

- Rule cards and the rule manager sidebar (`ui/rule_editor.py`)

- The custom toggle switch widget (`ui/styles/components.py`)

- Execution history timeline rows (`ui/history_view.py`)

- Settings tabs with animated indicator (`ui/settings.py`)

- Step-log pills (pending/running/done/failed states)

- Any new reusable widget in `ui/styles/components.py`

### Translation workflow

1. Invoke the MCP with a prompt describing the component and EdgeDesk's dark glassmorphism aesthetic (mention: near-black bg, purple-indigo accent `#7c6af7`, frosted glass cards, Inter font).

2. From the returned React/CSS output, extract:

   - Exact color values → map to design tokens in `ui/styles/theme.py`

   - Border-radius, padding, font-size values → verify against the 4px spacing grid and radius tokens

   - Animation durations and easing → re-implement as `QPropertyAnimation` or `QGraphicsEffect`

   - Hover/active/focus state deltas → translate to QSS pseudo-states (`:hover`, `:focus`, `:pressed`)

   - Box-shadow / glow values → recreate with `QGraphicsDropShadowEffect`

3. Implement the widget in PyQt6 + QSS, never in React.

4. If the MCP output introduces a new token (color, radius, shadow), add it to `ui/styles/theme.py` first.

### Prompt template for the MCP

```text
Dark glassmorphism desktop app (PyQt6, not web). Background #0a0a0f, surface #12121a,
accent #7c6af7, text #f0f0f8. Frosted glass cards with rgba(255,255,255,0.04) bg and
rgba(255,255,255,0.08) border. Inter font. Rounded corners 10-22px. 4px spacing grid.
Component needed: <describe the widget>
```

---

## Claude Code Workflow Instructions

When building this project, follow these patterns from the everything-claude-code system:

### Sub-agents to Use

When a task is complex, delegate to these sub-agent archetypes:

- **planner** — Break down a new feature into steps before coding

- **architect** — Decide module boundaries and data flow

- **tdd-guide** — Write tests before implementing a tool or schema

- **code-reviewer** — Review after completing a module

- **refactor-cleaner** — After a phase is complete, clean dead code

### Slash Commands to Use

- `/tdd` — When starting a new module (write tests first)

- `/plan` — Before implementing any multi-file feature

- `/code-review` — After completing core/ or tools/ modules

- `/refactor-clean` — At end of each development phase

- `/build-fix` — When tests fail or imports break

### Hooks Behavior

- PostToolUse on `.py` files: run `ruff format {file}` and `ruff check {file} --fix`

- PostToolUse on `.py` files: run `mypy {file} --ignore-missing-imports`

- PreToolUse on git push: show diff summary and ask for confirmation

- Stop hook: check for any `print()` statements remaining in `core/` or `tools/`

### Development Workflow

1. Always run `uv sync` before starting a session

2. Use `uv run pytest tests/ -v` to verify nothing is broken before committing

3. Commit with conventional commits: `feat:`, `fix:`, `refactor:`, `test:`, `docs:`

4. Never commit with failing tests

5. Keep `CLAUDE.md` updated if architecture changes

---

## Testing Standards

- Every tool in `tools/` must have a unit test with a mocked pyautogui/screen

- Every Pydantic schema must have validation tests (valid + invalid inputs)

- Agent planner tests use a mock LLM that returns scripted tool call sequences

- Target: 80% test coverage on `core/` and `tools/`

- Use `pytest-asyncio` for async tool tests

- Fixture pattern: create a fresh in-memory SQLite DB per test session

---

## Performance Rules

- Screen OCR: cache screenshots for 500ms — don't re-capture between consecutive tool calls in same step

- FAISS index: load once at startup, persist to disk every 10 new entries

- SQLAlchemy: use connection pool, never create new connections per-request

- LLM calls: always async with streaming — never blocking `invoke()` in UI thread

- PyAutoGUI: add `pyautogui.PAUSE = 0.05` (50ms between actions) for reliability

---

## Ollama Integration Details

```python
# Correct Ollama setup (core/llm.py)
from langchain_ollama import ChatOllama

llm = ChatOllama(
    model="mistral-nemo",         # or phi3.5 for low VRAM
    base_url="http://localhost:11434",
    temperature=0.1,              # Low temp for deterministic tool calls
    streaming=True,
    num_ctx=4096,                 # Context window
)
```

Available models (in order of preference by capability):

1. `mistral-nemo:12b` — Best tool calling, needs 8GB VRAM

2. `llama3.1:8b` — Good balance, 6GB VRAM  

3. `phi4:14b` — Excellent reasoning, 10GB VRAM

4. `phi3.5:3.8b` — Fallback for CPU/low-VRAM, 4GB RAM

---

## Absolute Rules (Never Break)

1. **No external API calls** — if you write `requests.get("https://...")` to any non-localhost URL, delete it

2. **No `os.system()` or `eval()`** — use subprocess with explicit args list

3. **No plaintext credentials** — all config via `.env` loaded with `python-dotenv`

4. **No blocking UI thread** — all async work via `QThread` or `asyncio` with Qt event loop integration (use `qasync`)

5. **No magic numbers in UI** — always use design token constants from `ui/styles/theme.py`

6. **No default PyQt6 widget styling** — every widget MUST have QSS applied

7. **No unnecessary dependencies** — check if stdlib covers it before adding a package

8. **No print debugging in commits** — use `loguru.logger.debug()` exclusively

---

## Quick Reference: Key Libraries

```toml
# pyproject.toml dependencies
[project]
dependencies = [
    "langchain>=0.3.0",
    "langchain-ollama>=0.2.0",
    "langchain-community>=0.3.0",
    "pyautogui>=0.9.54",
    "keyboard>=0.13.5",
    "mouse>=0.7.1",
    "mss>=9.0.0",
    "pytesseract>=0.3.13",
    "pyqt6>=6.7.0",
    "qtawesome>=1.3.1",
    "qasync>=0.27.1",
    "sqlalchemy>=2.0.0",
    "pydantic>=2.7.0",
    "apscheduler>=3.10.0",
    "sentence-transformers>=3.0.0",
    "faiss-cpu>=1.8.0",
    "pyperclip>=1.9.0",
    "plyer>=2.1.0",
    "watchdog>=4.0.0",
    "psutil>=6.0.0",
    "loguru>=0.7.0",
    "python-dotenv>=1.0.0",
    "rich>=13.7.0",
]
```

---

## Implementation Plan

> **How to use this plan:**
>
> - Status markers: `[ NOT STARTED ]` → `[ IN PROGRESS ]` → `[ COMPLETE ✓ ]`
> - Update this section as each phase finishes. Mark completed tasks with `✓`, note blockers inline.
> - The **"Next"** line at the end of each phase tells the next Claude session exactly where to pick up.
> - Run `/plan` before starting any phase. Run `/tdd` for every file. Run `/python-review` after every phase.

---

### Phase 1 — Project Scaffold & Dev Infrastructure `[ COMPLETE ✓ ]`

**Goal:** Runnable project skeleton with linting, formatting, and test config wired up. Nothing functional yet.

**Files to create:**

- `pyproject.toml` — uv project config, all deps from Quick Reference + dev deps: `ruff`, `mypy`, `pytest`, `pytest-asyncio`, `pytest-cov`, `aiosqlite>=0.20.0`

- `ruff.toml` — line-length=100, target-version=py312, isort enabled

- `.env.example` — `OLLAMA_MODEL=mistral-nemo`, `OLLAMA_BASE_URL=http://localhost:11434`, `DATA_DIR=~/.edgedesk`

- `main.py` — stub only: imports, `if __name__ == "__main__": pass`

- `conftest.py` — root-level pytest fixtures: `tmp_path` override, `event_loop` for asyncio

- `tests/__init__.py`, `tests/conftest.py` — in-memory SQLite session fixture

**Config in pyproject.toml:**

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.mypy]
python_version = "3.12"
strict = false
ignore_missing_imports = true
```

**Exit criteria:**

- [x] `uv sync` completes with no errors

- [x] `uv run ruff check .` passes on empty stubs

- [x] `uv run pytest tests/ -v` runs (0 tests, no errors)

**Next →** Phase 2: Data Layer

---

### Phase 2 — Data Layer: SQLAlchemy Models + Pydantic Schemas `[ COMPLETE ✓ ]`

**Goal:** All database models, CRUD ops, FAISS vector store, and Pydantic I/O schemas defined before any agent code.

**Files to create:**

- `db/models.py` — SQLAlchemy 2.x models: `Rule`, `Execution` (match PRD section 9 exactly). Use `mapped_column`, `Mapped` typing, `UUID` primary keys, `JSON` columns for `trigger_config`, `steps`, `steps_log`. Add `AgentMemoryRecord` model too.

- `db/crud.py` — async CRUD: `create_rule`, `get_rule`, `list_rules`, `update_rule`, `delete_rule`, `create_execution`, `list_executions`, `update_feedback`. Use `AsyncSession`.

- `db/session.py` — engine factory: `create_async_engine("sqlite+aiosqlite:///...")`, connection pool, `get_session` async context manager. Creates `~/.edgedesk/` dir on first run.

- `db/vector_store.py` — `VectorStore` class: loads `all-MiniLM-L6-v2`, `add_rule(rule_id, text)`, `search(query, k=5)`, auto-persist every 10 inserts to `~/.edgedesk/rules.faiss`

- `schemas/models.py` — Pydantic v2 models for every tool I/O:

  - `ScreenCaptureInput` / `ScreenCaptureOutput`

  - `GUIClickInput`, `GUITypeInput`, `GUIScrollInput` / `GUIActionOutput`

  - `FileReadInput/Output`, `FileWriteInput`, `FileMoveInput/Output`

  - `AppLaunchInput/Output`

  - `ClipboardReadOutput`, `ClipboardWriteInput`

  - `NotifyInput`

  - `EmailListInput/Output`

  - `ToolError` — `tool: str`, `message: str`, `retryable: bool`

- `tests/test_db.py` — test every CRUD op + schema validation (valid + invalid inputs)

**Key rules:**

- All timestamps: `datetime.utcnow()` stored as ISO strings

- `db/session.py` must call `Base.metadata.create_all(engine)` on first connect

**Exit criteria:**

- [x] `uv run pytest tests/test_db.py -v` — all pass (49/49)

- [x] `uv run mypy db/ schemas/ --ignore-missing-imports` — no errors (7 source files)

- [x] All Pydantic schemas have valid + invalid input tests

**Next →** Phase 3: Core Agent

---

### Phase 3 — Core Agent: LLM + ReAct + Memory `[ COMPLETE ✓ ]`

**Goal:** A working LangChain ReAct agent that reasons through instructions using mock tools. No real GUI automation yet.

**Files to create:**

- `core/llm.py` — `OllamaLLM` class:

  - Detect VRAM via `subprocess.run(["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"])`

  - Select model: `>= 8192 MB → mistral-nemo:12b`, else `phi3.5:3.8b`

  - Returns `ChatOllama(model=..., base_url=..., temperature=0.1, streaming=True, num_ctx=4096)`

  - Health check: `GET localhost:11434/api/tags` — raise `ConnectionError` if Ollama not running

- `core/memory.py` — `AgentMemory` class:

  - Wraps `ConversationSummaryBufferMemory(max_token_limit=2000, llm=llm)`

  - Persists summary to `AgentMemoryRecord` SQLite table

  - `async save()`, `async load()`, `clear()`

- `core/prompts.py` — `REACT_SYSTEM_PROMPT` constant: includes `{current_datetime}`, `{available_tools}`, privacy reminder ("no external calls")

- `core/agent.py` — `AgentOrchestrator` class:

  - Uses `create_react_agent(llm, tools, prompt)` — NOT deprecated `initialize_agent`

  - `async run(instruction: str) -> AsyncIterator[str]` — streams tokens via `AsyncIteratorCallbackHandler`

  - Catches `OutputParserException`, returns `ToolError`

  - Singleton: initialized once in `main.py`

- `core/planner.py` — `TaskPlanner.decompose(instruction) -> list[str]` — LLM breaks task into ordered sub-steps

- `tests/test_agent.py` — mock LLM returning scripted tool call sequences, test full ReAct loop

**Key rules:**

- Never call `llm.invoke()` synchronously — always `await llm.ainvoke()`

- `AgentOrchestrator` receives `TOOL_MANIFEST` from `tools/__init__.py` — never imports tools directly

**Exit criteria:**

- [x] `uv run pytest tests/test_agent.py -v` — all pass with mock LLM (26/26)

- [x] Ollama health check raises `ConnectionError` correctly when Ollama is offline

- [x] Streaming works: tokens emitted one-by-one via async iterator

> **Note:** `langgraph.prebuilt.create_react_agent` is deprecated in langgraph v1.0+. The new
> location is `langchain.agents.create_agent` but its signature differs. Current code uses the
> deprecated shim (still fully functional). Migrate in Phase 9 if langgraph v2 is released.

**Next →** Phase 4: Desktop Tools

---

### Phase 4 — Desktop Tools (All 7) `[ COMPLETE ✓ ]`

**Goal:** All 7 LangChain `BaseTool` subclasses with Pydantic schemas, retry logic, and mocked unit tests.

**Files to create:**

- `tools/screen.py` — `ScreenTool`: `mss` screenshot → `pytesseract.image_to_string`. 500ms LRU cache keyed to timestamp bucket.

- `tools/gui.py` — `GUITool`: `pyautogui.PAUSE = 0.05` at module level. Retry decorator: max 3 attempts, `0.5s * 2^n` backoff. Verify click landed via re-capture OCR.

- `tools/files.py` — `FileTool`: read/write/move/delete/list. Reject paths containing `..`.

- `tools/apps.py` — `AppTool`: `subprocess.Popen(args_list)` launch, `psutil.process_iter` list.

- `tools/clipboard.py` — `ClipboardTool`: `pyperclip.copy/paste`.

- `tools/notify.py` — `NotifyTool`: `plyer.notification.notify(title, message, timeout=5)`.

- `tools/email_reader.py` — `EmailTool`: `imaplib.IMAP4_SSL`, credentials from `.env`.

- `tools/__init__.py` — exports `TOOL_MANIFEST: list[BaseTool]` — all 7 tools instantiated.

- `tests/test_tools.py` — mock `pyautogui`, `mss`, `pytesseract`, `pyperclip`, `plyer`. Test every action + retry behavior.

**Key rules:**

- Every `_run` returns `ToolError | <OutputModel>` — never raises to agent

- Every tool: `name` + `description` (< 100 chars, action-verb first) + `args_schema`

- `tools/gui.py`: wrap every call in `try/except pyautogui.FailSafeException`

**Exit criteria:**

- [x] `uv run pytest tests/test_tools.py -v` — all pass (47/47), mocks verified

- [x] `/python-review` on each tool file — no HIGH issues

- [x] `from tools import TOOL_MANIFEST` works cleanly

**Next →** Phase 5: Scheduler + Rules Engine

---

### Phase 5 — Scheduler + Rules Engine `[ COMPLETE ✓ ]`

**Goal:** APScheduler wired to SQLite rules. Three trigger types: cron, file-watch, manual.

**Files to create:**

- `scheduler/engine.py` — `SchedulerEngine`:

  - `AsyncIOScheduler` from APScheduler

  - `async start()` — loads all enabled rules from DB, registers jobs

  - `async stop()`

  - `async reload_rule(rule_id)` — add/update/remove job for a single rule

  - Job callback: `async _fire_rule(rule_id, orchestrator)` → calls `AgentOrchestrator.run(rule.instruction)` → logs to `executions` table

- `scheduler/triggers.py` — `make_trigger(rule) -> BaseTrigger`:

  - `time_cron` → `CronTrigger(**rule.trigger_config)`

  - `file_event` → `IntervalTrigger(seconds=30)` + `watchdog.Observer`

  - `manual` → fires once immediately

- `tests/test_scheduler.py` — test job registration, mock orchestrator firing, enable/disable

**Exit criteria:**

- [x] `uv run pytest tests/test_scheduler.py -v` — all pass (25/25)

- [x] Cron job fires at correct time using explicit `now` param on `get_next_fire_time()` (freeze_time equivalent, no extra dep)

- [x] Every job fire creates an execution record in DB

**Next →** Phase 6: UI Design System

---

### Phase 6 — UI Design System & Reusable Widgets `[ COMPLETE ✓ ]`

**Goal:** Design tokens defined, reusable widget primitives built. No application screens yet — component library only.

**Files to create:**

- `ui/styles/theme.py` — all design tokens from the Design Tokens section. `apply_font(app: QApplication)` loads Inter from `ui/assets/fonts/`

- `ui/styles/qss.py` — QSS template functions: `glass_card_qss(radius)`, `input_field_qss()`, `scrollbar_qss()`, `button_qss(variant)`

- `ui/styles/components.py` — custom widgets (invoke **21st.dev MCP** before each):

  - `GlassCard(QFrame)` — glass bg + border + drop shadow

  - `ToggleSwitch(QAbstractButton)` — custom painted, `QPropertyAnimation` on float `0.0→1.0` for knob

  - `StepPill(QWidget)` — icon + label + `StatusDot`, animated opacity pulse (800ms loop) when `status == "running"`

  - `StatusDot(QWidget)` — 8px colored circle with optional pulse

  - `AccentButton(QPushButton)` — primary/ghost variants with hover glow

  - `AnimatedTabBar(QWidget)` — sliding underline indicator via `QPropertyAnimation`

- `ui/assets/fonts/` — Inter (Regular, Medium, SemiBold) + JetBrains Mono Regular

- Each widget must have a `if __name__ == "__main__"` demo block for visual testing

**Exit criteria:**

- [x] `from ui.styles.components import GlassCard, ToggleSwitch, StepPill` — no crash

- [x] Visual demo runs: `uv run python ui/styles/components.py`

- [x] No magic number colors or radii anywhere — all use theme constants

**Next →** Phase 7: Command Overlay

---

### Phase 7 — Command Overlay (ui/overlay.py) `[ COMPLETE ✓ ]`

**Goal:** The core UX. Frameless glass window on `Alt+Space`, streams agent output as step pills, dismisses on `Esc` or click-outside.

**Files to create:**

- `ui/overlay.py` — `OverlayWindow(QWidget)`:

  - Flags: `FramelessWindowHint | WindowStaysOnTopHint | Tool`

  - Windows DWM acrylic blur via `ctypes` calling `DwmExtendFrameIntoClientArea` (Windows only, graceful fallback)

  - Width 680px, `RADIUS_XL` corners, centered on primary screen

  - Layout: `QVBoxLayout` → `InputBar` (48px) → `StepLogArea` (scrollable, max 400px, hidden when empty)

  - `InputBar(QLineEdit)` subclass: transparent bg, animated 2px bottom border on focus via `QPropertyAnimation`

  - `StepLogArea(QScrollArea)`: wraps `QVBoxLayout` of `StepPill` widgets, height-animates open (0 → content height, 150ms)

  - Show animation: opacity `0→1` + y-offset `+20→0`, 180ms `OutCubic` easing

  - Dismiss: `Esc` keypress OR `eventFilter` on `QApplication` for click-outside

  - Signals: `instruction_submitted(str)` on Enter → connected to `AgentOrchestrator.run()`

  - Slots: `on_token(token)` appends to current step pill; `on_step_update(step_id, status, text)` creates/updates `StepPill`

  - Input + step log clear on each new open

**Key rules:**

- `OverlayWindow` never creates `AgentOrchestrator` — receives it as constructor arg

- DWM calls only on `sys.platform == "win32"`, wrapped in `try/except`

- All Qt ↔ asyncio bridging via `qasync`

**Exit criteria:**

- [x] Opens on `Alt+Space` (hotkey registered via `core/hotkey.py` `HotkeyManager`)

- [x] Typing + Enter emits signal with correct instruction text

- [x] Step pills appear, pulse while running, turn green/red on done/failed

- [x] Dismisses cleanly on `Esc` and click-outside

**Next →** Phase 8: Management Panels

---

### Phase 8 — Management UI Panels `[ COMPLETE ✓ ]`

**Goal:** Rule manager, execution history, and settings — all reachable from the system tray.

**Files to create:**

- `ui/rule_editor.py` — `RuleManagerPanel(QWidget)` (use MCP for card + slide-in):

  - Left `QListWidget`: each item renders `RuleCard(GlassCard)` — name, trigger-type badge, `ToggleSwitch`, run count

  - `RuleCard` hover: `BG_ELEVATED` + 2px `ACCENT_PRIMARY` left border via QSS

  - Right `QStackedWidget`: empty state | `RuleDetailEditor`

  - `RuleDetailEditor`: name, description, trigger-type `QComboBox`, JSON config `QPlainTextEdit`, save/delete buttons

  - Slide-in: right panel x+200 → x, 200ms `OutCubic`

- `ui/history_view.py` — `HistoryView(QWidget)` (use MCP for timeline row):

  - Sticky date-group headers (`QLabel`, `BG_PRIMARY` bg)

  - `HistoryRow(GlassCard)`: timestamp, rule chip, `StatusDot`, duration, thumbs ±1 buttons

  - Expand row on click → reveals `StepPill` list

  - Paginates on scroll: `list_executions(limit=100, offset=n)`

- `ui/settings.py` — `SettingsDialog(QDialog)` — 640×480px:

  - `AnimatedTabBar`: General · LLM · Hotkeys · Privacy

  - LLM tab: model `QComboBox` (queries `localhost:11434/api/tags`), VRAM label, `num_ctx` slider

  - Hotkeys tab: `QKeySequenceEdit` for overlay hotkey

  - Privacy tab: "Clear history" + "Export data" buttons

  - Saves to `.env` via `dotenv.set_key()`

- `ui/tray.py` — `SystemTrayApp(QSystemTrayIcon)`:

  - Context menu: Open Overlay · Rules · History · Settings · Quit

  - Shows balloon notification on first launch + on scheduler job completion

**Exit criteria:**

- [x] All panels open from tray without crash

- [x] Rule toggle persists after app restart (via rule_toggled signal → Phase 9 DB write)

- [x] Feedback buttons write to DB correctly (via feedback_given signal → Phase 9 DB write)

- [x] Settings round-trip: save → restart → values restored (tested with tmp .env)

**Next →** Phase 9: Full Integration

---

### Phase 9 — Full Integration & main.py `[ COMPLETE ✓ ]`

**Goal:** Wire every component together in a single boot sequence using `qasync`.

**Files to create/modify:**

- `main.py` — boot sequence (in order):

  1. `load_dotenv()` from `.env`

  2. Init DB session + `Base.metadata.create_all(engine)`

  3. Load `VectorStore` from disk

  4. Ollama health check — show tray balloon error if down, continue anyway

  5. Build `OllamaLLM` → `AgentMemory` → `AgentOrchestrator`

  6. Build `SchedulerEngine`, load rules, `await scheduler.start()`

  7. Build `QApplication`, set `qasync.QEventLoop` as the event loop

  8. Build `SystemTrayApp` + `OverlayWindow` (pass orchestrator)

  9. Register `Alt+Space` hotkey via `HotkeyManager`

  10. Start Qt event loop via `qasync.run()`

- `core/hotkey.py` — `HotkeyManager`: wraps `keyboard.add_hotkey("alt+space", callback)`, emits signal to Qt main thread via `QMetaObject.invokeMethod`

- `tests/test_integration.py` — full boot with mock Ollama + mock pyautogui + in-memory DB; submit instruction, verify execution logged

**Key rules:**

- All `asyncio.create_task()` calls happen after `QApplication` + `QEventLoop` are created

- `keyboard` library runs in a thread — never call Qt from it directly, only via signals

- Graceful shutdown: `scheduler.stop()` → `memory.save()` → `QApplication.quit()`

**Exit criteria:**

- [x] `uv run python main.py` launches to tray without crash

- [x] `Alt+Space` opens overlay

- [x] Instruction → token stream → step pills → execution in history view

- [x] Clean shutdown on tray "Quit"

**Next →** Phase 10: Polish + Packaging

---

### Phase 10 — Polish, Full Tests & Packaging `[ NOT STARTED ]`

**Goal:** 80%+ test coverage, all performance targets met, single-file executable produced.

**Tasks:**

- **Coverage audit:** `uv run pytest --cov=core --cov=tools --cov=db --cov=scheduler --cov-report=term-missing` — reach 80%+ on `core/` + `tools/`

- **Retry logic audit:** verify all GUI tools retry 3× with backoff; add `tests/test_retry.py`

- **Performance checks:**

  - OCR 500ms cache: timing assertion in `tests/test_tools.py`

  - FAISS persist every 10 inserts: counter assertion in `tests/test_db.py`

  - Startup < 2s: manual tray-icon timing check

- **UI polish:** `/code-review` on all `ui/` files; fix any visual rule violations

- **Packaging:** create `edgedesk.spec` for PyInstaller — bundles `ui/assets/`, `ui/styles/`, `.env.example`, Tesseract data files

- **README.md:** install steps (Ollama, uv, model pull, `uv sync`, run)

- **Final sweep:** `/refactor-clean` across entire codebase → `/quality-gate` → tag `v1.0.0`

**Exit criteria:**

- [ ] `uv run pytest --cov` → ≥ 80% on `core/` + `tools/`

- [ ] `uv run ruff check . && uv run mypy . --ignore-missing-imports` — both clean

- [ ] PyInstaller produces working binary

- [ ] All 5 use cases from PRD §8 manually tested end-to-end

**Next →** Tag `v1.0.0`, write release notes.

---

### Current Status

```text
Phase 1  — Scaffold            [ COMPLETE ✓ ]
Phase 2  — Data Layer          [ COMPLETE ✓ ]
Phase 3  — Core Agent          [ COMPLETE ✓ ]
Phase 4  — Desktop Tools       [ COMPLETE ✓ ]
Phase 5  — Scheduler + Rules   [ COMPLETE ✓ ]
Phase 6  — UI Design System    [ COMPLETE ✓ ]
Phase 7  — Command Overlay     [ COMPLETE ✓ ]
Phase 8  — Management Panels   [ COMPLETE ✓ ]
Phase 9  — Full Integration    [ COMPLETE ✓ ]
Phase 10 — Polish + Packaging  [ NOT STARTED ]
```

> **For future Claude sessions:** Read the Current Status table first → find the first `[ NOT STARTED ]` or `[ IN PROGRESS ]` phase → read that phase's "Files to create" and "Exit criteria" → run `/plan` to confirm scope → run `/tdd` per file → when phase is complete, mark `[ COMPLETE ✓ ]`, update this table, verify the "Next →" pointer is correct.

---

*EdgeDesk CLAUDE.md v1.1 | Eko | PSG College of Technology, Coimbatore*
*Keep this file updated as architecture evolves. This is the source of truth for Claude Code.*
