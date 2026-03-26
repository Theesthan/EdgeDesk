# PRD.md — EdgeDesk: Local AI Agent for Privacy-First Desktop Automation

## 1. Project Overview

**Product Name:** EdgeDesk  
**Version:** 1.0.0  
**Author:** Eko (PSG College of Technology, Coimbatore)  
**Date:** March 2026  
**Status:** In Development

EdgeDesk is a fully local, privacy-first AI desktop automation agent. It accepts natural-language instructions and autonomously executes multi-step workflows across any desktop application using on-device LLMs, an agent planning framework, and OS-level GUI control libraries — entirely without cloud APIs or subscription costs.

---

## 2. Problem Statement

Modern desktop automation tools (Zapier, Make, AutoHotkey) are either cloud-dependent, require scripting expertise, or can only act on structured data. Users who want intelligent, context-aware automation of their desktop — like "summarise today's emails and put it in Notion" — have no privacy-first, free, conversational option. EdgeDesk solves this by combining local LLMs with agentic planning and GUI interaction, giving power-user capabilities to anyone while keeping all data on-device.

---

## 3. Goals & Non-Goals

### Goals
- Natural-language workflow automation across arbitrary desktop apps
- Full local execution — no internet required after setup
- Zero per-use cost — all open-source or free-tier tooling
- Persistent automation rules that run on schedule or trigger
- Adaptive behavior via user feedback stored in local SQLite
- Cross-platform: Windows 10/11 primary, Linux secondary

### Non-Goals
- Cloud/remote execution of any kind
- Mobile platforms
- Paid LLM API integration (Anthropic, OpenAI) — out of scope for v1
- Browser automation as primary use case (Playwright/Selenium not primary)

---

## 4. Target Users

| Persona | Need |
|---|---|
| Power User / Developer | Automate repetitive file/app workflows without scripting |
| Student | Auto-schedule planners, take notes, organize study material |
| Remote Worker | Draft email replies, fill forms, manage local files intelligently |
| Privacy-Conscious User | All above without any data leaving the machine |

---

## 5. Core Features

### 5.1 Natural Language Instruction Interface
- PyQt6-based system tray app with a chat-style input overlay (global hotkey: `Alt+Space`)
- Users type or speak instructions in plain English
- Displays current task, sub-steps, and execution log in real-time

### 5.2 Local LLM Brain
- LLM served locally via **Ollama** (recommended: `mistral-nemo:12b`, `llama3.1:8b`, or `phi4:14b`)
- Model context managed by **LangChain** + custom prompt templates
- Falls back to smaller model (phi3.5:3.8b) on low-VRAM machines
- LLM streaming output piped to UI for live feedback

### 5.3 Agentic Planning Engine
- **LangChain ReAct agent** for multi-step reasoning (Reason → Act → Observe loop)
- Agent receives a tool manifest and chooses appropriate tools per step
- Sub-agent pattern for isolated task delegation (e.g. email sub-agent, file sub-agent)
- Agent memory uses **LangChain ConversationSummaryBufferMemory** backed by SQLite

### 5.4 Desktop Control Toolkit (Tools)
| Tool | Library | Capability |
|---|---|---|
| Screen Reader | `mss` + `pytesseract` | Screenshot + OCR to understand screen state |
| GUI Interaction | `pyautogui` + `keyboard` + `mouse` | Click, type, scroll, hotkeys |
| App Launcher | `subprocess` + `psutil` | Open/close/focus applications |
| File Manager | `pathlib` + `shutil` + `watchdog` | Create, move, delete, monitor files |
| Clipboard | `pyperclip` | Read/write clipboard |
| Notification | `plyer` | System tray notifications and alerts |
| Email Reader | `imaplib` + `email` | Read local IMAP email (offline-ready) |
| Scheduler | `APScheduler` | Cron-style and interval-based triggers |
| Vision (Optional) | `florence2` via Ollama | UI element detection without coordinates |

### 5.5 Automation Rules Engine
- Users can "save" successful workflows as named rules (e.g., "morning_planner")
- Rules stored as JSON in SQLite with: trigger type, steps, success rate, last run
- Trigger types: `time_cron`, `file_event`, `app_event`, `manual`
- Rules editor in UI with enable/disable toggle per rule

### 5.6 Execution History & Feedback Loop
- Every execution logged: timestamp, rule name, steps taken, success/fail, duration
- User can thumbs-up/down each run — feedback stored and used in system prompt
- Pydantic models validate all agent tool call I/O
- Retry logic with exponential backoff for failed GUI actions

### 5.7 Local Storage Layer
- **SQLite** (via `SQLAlchemy` ORM) for: rules, execution history, user feedback, app config
- **FAISS** vector store for semantic rule search ("find automation similar to my file organizer")
- **sentence-transformers** (`all-MiniLM-L6-v2`) for local embeddings — no API needed

---

## 6. Technical Architecture

```
┌─────────────────────────────────────────────────┐
│                  EDGEDESK UI                    │
│   PyQt6 System Tray + Chat Overlay (Alt+Space)  │
│   Real-time step log, rule manager, settings    │
└───────────────┬────────────────────────────────-┘
                │ NL Instruction
                ▼
┌─────────────────────────────────────────────────┐
│              AGENT ORCHESTRATOR                 │
│  LangChain ReAct Agent + Custom Tool Manifest   │
│  ConversationSummaryBufferMemory (SQLite)       │
│  Pydantic I/O Schemas + Error Recovery          │
└────────┬─────────────────────────┬──────────────┘
         │ LLM calls               │ Tool calls
         ▼                         ▼
┌─────────────────┐    ┌──────────────────────────┐
│   LOCAL LLM     │    │    DESKTOP TOOL BELT      │
│  Ollama HTTP    │    │  pyautogui / keyboard     │
│  Mistral/Llama  │    │  mss + pytesseract (OCR)  │
│  Phi / Gemma    │    │  imaplib / email          │
└─────────────────┘    │  APScheduler              │
                       │  plyer (notifications)    │
                       │  pathlib / watchdog       │
                       └──────────────┬───────────┘
                                      │
                       ┌──────────────▼───────────┐
                       │    LOCAL DATA LAYER       │
                       │  SQLite (SQLAlchemy ORM)  │
                       │  FAISS + sentence-xformers│
                       │  Rules / History / Prefs  │
                       └──────────────────────────┘
```

---

## 7. Tech Stack

### Core Stack
| Layer | Technology | Why |
|---|---|---|
| Language | Python 3.12 | Best ecosystem for AI + GUI automation |
| UI Framework | PyQt6 | Native performance, system tray, custom widgets |
| LLM Runtime | Ollama (local HTTP) | Free, simple, supports quantized models |
| Agent Framework | LangChain 0.3.x | ReAct agents, tool binding, memory |
| GUI Automation | PyAutoGUI 0.9.x + `keyboard` + `mouse` | Cross-platform screen control |
| Screen Capture | mss (fast) + pytesseract (OCR) | Read screen state without element trees |
| Scheduler | APScheduler 3.x | Cron + interval triggers |
| ORM | SQLAlchemy 2.x | Type-safe SQLite access |
| Validation | Pydantic v2 | Agent I/O schema enforcement |
| Embeddings | sentence-transformers (local) | Rule semantic search, no API |
| Vector Store | FAISS (CPU) | Fast local similarity search |
| Notifications | plyer | System-native alerts |
| Config | python-dotenv + TOML | User settings file |
| Packaging | PyInstaller | Single .exe / AppImage distribution |

### Dev Tools
| Tool | Purpose |
|---|---|
| uv (Astral) | Ultra-fast dependency management (replaces pip/venv) |
| Ruff | Linting + formatting (replaces black/flake8) |
| pytest + pytest-asyncio | Testing agent logic |
| loguru | Structured logging |
| rich | Beautiful terminal output for CLI mode |

---

## 8. Example Automations (Use Cases)

### UC-01: Smart Email Reply Draft
**Trigger:** Manual ("Generate a reply to John's email about the project deadline")  
**Steps:**
1. Agent opens mail client (Thunderbird/Gmail webapp)
2. OCR finds John's email, extracts text
3. LLM drafts a contextually appropriate reply
4. Agent pastes draft into compose window
5. Saves as draft, notifies user

### UC-02: Morning Planner Creator
**Trigger:** Cron — weekdays 9:00 AM  
**Steps:**
1. Opens Obsidian/Notion/Notepad
2. Reads yesterday's notes (file path from config)
3. LLM generates a structured daily plan
4. Creates new dated file, pastes content
5. System notification: "Today's planner is ready"

### UC-03: Code Summariser → Desktop Saver
**Trigger:** Manual ("Summarise the open VS Code file and save to Desktop")  
**Steps:**
1. Gets active window title, identifies VS Code
2. Ctrl+A, Ctrl+C to copy all code
3. LLM generates summary + docstring header
4. Opens Notepad, pastes summary
5. Ctrl+S, saves to `~/Desktop/summary_{date}.txt`

### UC-04: File Organiser
**Trigger:** File event — new file in `~/Downloads`  
**Steps:**
1. watchdog detects new file
2. LLM classifies file type from name/extension
3. Moves to appropriate folder (Documents/Media/Projects/Archives)
4. Logs action to history

### UC-05: App Session Saver
**Trigger:** Manual ("Save my current workspace")  
**Steps:**
1. Enumerates open applications via psutil
2. Reads open file tabs from supported apps
3. Saves session snapshot as JSON to `~/.edgedesk/sessions/`
4. Can restore session on command

---

## 9. Data Model

### rules table
```sql
CREATE TABLE rules (
    id TEXT PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    trigger_type TEXT,       -- time_cron | file_event | manual
    trigger_config JSON,
    steps JSON,
    enabled BOOLEAN DEFAULT 1,
    success_rate REAL DEFAULT 0.0,
    run_count INTEGER DEFAULT 0,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

### executions table
```sql
CREATE TABLE executions (
    id TEXT PRIMARY KEY,
    rule_id TEXT REFERENCES rules(id),
    instruction TEXT,
    steps_log JSON,
    status TEXT,             -- success | partial | failed
    feedback INTEGER,        -- 1=good, -1=bad, 0=none
    duration_ms INTEGER,
    executed_at TIMESTAMP
);
```

---

## 10. Project Structure

```
edgedesk/
├── main.py                  # Entry point, system tray init
├── pyproject.toml           # uv project config
├── .env                     # User settings (OLLAMA_MODEL, etc.)
├── CLAUDE.md                # Claude Code context file
├── PRD.md                   # This file
│
├── core/
│   ├── agent.py             # LangChain ReAct agent setup
│   ├── llm.py               # Ollama connection, model switching
│   ├── memory.py            # SQLite-backed agent memory
│   └── planner.py           # Multi-step plan decomposition
│
├── tools/
│   ├── screen.py            # mss screenshot + pytesseract OCR
│   ├── gui.py               # pyautogui + keyboard + mouse
│   ├── files.py             # pathlib file operations
│   ├── apps.py              # subprocess app launcher
│   ├── email_reader.py      # imaplib email tool
│   ├── clipboard.py         # pyperclip wrapper
│   └── notify.py            # plyer notifications
│
├── scheduler/
│   ├── engine.py            # APScheduler setup
│   └── triggers.py          # Cron, file, app event triggers
│
├── db/
│   ├── models.py            # SQLAlchemy models
│   ├── crud.py              # DB operations
│   └── vector_store.py      # FAISS + sentence-transformers
│
├── ui/
│   ├── tray.py              # System tray app
│   ├── overlay.py           # Alt+Space chat overlay
│   ├── rule_editor.py       # Rule management panel
│   ├── history_view.py      # Execution history
│   ├── settings.py          # Settings dialog
│   └── styles/
│       ├── theme.py         # Color tokens + design system
│       └── components.py    # Reusable PyQt6 widgets
│
├── schemas/
│   └── models.py            # Pydantic v2 schemas
│
└── tests/
    ├── test_agent.py
    ├── test_tools.py
    └── test_scheduler.py
```

---

## 11. Non-Functional Requirements

| Requirement | Target |
|---|---|
| LLM Response Latency | < 3s for first token (Mistral 7B Q4 on 8GB VRAM) |
| GUI Action Precision | > 95% accurate click targeting via coordinate + OCR verification |
| Scheduler Accuracy | ± 1 second for cron triggers |
| Startup Time | < 2 seconds for tray icon |
| Memory Usage | < 500MB RAM (agent only, excluding LLM) |
| Storage | < 50MB for app + DB (excluding models) |
| Offline Operation | 100% after initial model download |

---

## 12. Development Phases

### Phase 1 — Core Agent (Weeks 1-2)
- Ollama integration + LangChain ReAct agent
- Basic tool set: screen OCR, GUI control, clipboard
- CLI-mode execution of simple 1-3 step workflows
- SQLite setup for execution logging

### Phase 2 — Scheduler + Rules (Weeks 3-4)
- APScheduler integration (cron + file triggers)
- Rules storage, save/load from SQLite
- Watchdog file event triggers
- Basic PyQt6 system tray + rule list view

### Phase 3 — Full UI + Feedback (Weeks 5-6)
- Alt+Space overlay with chat input
- Real-time step log in UI
- User feedback (thumbs up/down) per execution
- FAISS semantic rule search
- Settings panel (model selection, hotkeys)

### Phase 4 — Polish + Packaging (Weeks 7-8)
- PyInstaller single-file build
- Dark mode glassmorphism UI polish
- Error recovery + retry logic
- Comprehensive test suite
- README + install docs

---

## 13. Installation & Setup

```bash
# Prerequisites: Python 3.12+, Ollama installed
# Install Ollama: https://ollama.com

# Pull a model
ollama pull mistral-nemo

# Clone and setup project
git clone https://github.com/eko/edgedesk
cd edgedesk
pip install uv
uv sync

# Configure
cp .env.example .env
# Edit .env: set OLLAMA_MODEL=mistral-nemo

# Run
uv run python main.py
```

---

## 14. Privacy & Security

- Zero network calls after model download — verified by no `requests` calls to external hosts in production
- All SQLite data stored in `~/.edgedesk/` — user-controlled
- No telemetry, no analytics, no auto-update pings
- GUI automation requires explicit user permission on macOS (Accessibility API)
- Agent tool calls validated by Pydantic before execution — no arbitrary code exec

---

*EdgeDesk PRD v1.0 | Eko | PSG College of Technology*
