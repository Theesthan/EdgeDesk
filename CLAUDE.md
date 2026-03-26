# CLAUDE.md — EdgeDesk

This file is the primary context document for Claude Code when working on the EdgeDesk project. Read this fully before writing any code. Every rule here is non-negotiable.

---

## Project Identity

**EdgeDesk** is a local, privacy-first AI desktop automation agent for Windows/Linux. It uses on-device LLMs (via Ollama), LangChain ReAct agents, and GUI automation libraries to execute natural-language instructions across desktop applications.

**Core constraint:** Zero external API calls in production. All LLM inference runs through the local Ollama HTTP server (localhost:11434).

**Stack summary:** Python 3.12 · PyQt6 · LangChain 0.3 · Ollama · PyAutoGUI · SQLAlchemy · Pydantic v2 · APScheduler · FAISS · sentence-transformers

---

## Architecture Map

```
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

## Memory & Context Management

- Use `/compact` when context exceeds 60% — always before starting a new module
- Use `@` file references to load specific files rather than asking Claude to explore
- Keep active context to: current module file + its schema + its test file
- Use `/fork` for parallel work: e.g., UI development and agent testing simultaneously
- Git worktrees for parallel feature branches: `git worktree add ../edgedesk-ui ui-branch`

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

*EdgeDesk CLAUDE.md v1.0 | Eko | PSG College of Technology, Coimbatore*
*Keep this file updated as architecture evolves. This is the source of truth for Claude Code.*
