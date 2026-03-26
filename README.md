# EdgeDesk

Local, privacy-first AI desktop automation agent for Windows/Linux.
Zero external API calls — all inference runs on-device via [Ollama](https://ollama.com).

---

## Prerequisites

| Requirement | Version |
|---|---|
| Python | 3.12+ |
| [uv](https://docs.astral.sh/uv/) | latest |
| [Ollama](https://ollama.com/download) | latest |
| [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) | 5.x |

---

## Installation

```bash
# 1. Clone the repo
git clone <repo-url>
cd EdgeDesk

# 2. Install Python dependencies
uv sync

# 3. Configure environment
cp .env.example .env
# Edit .env — set OLLAMA_MODEL, OLLAMA_BASE_URL, DATA_DIR as needed

# 4. Pull the LLM model
ollama pull mistral-nemo       # best quality (needs ~8 GB VRAM)
# or
ollama pull phi3.5             # low-VRAM fallback (~4 GB RAM)
```

---

## Running

```bash
# Start Ollama (in a separate terminal, or as a background service)
ollama serve

# Launch EdgeDesk
uv run python main.py
```

EdgeDesk starts silently in the system tray. Press **Alt+Space** to open the command overlay.

---

## Tray Menu

| Item | Action |
|---|---|
| Open Overlay | Show the command overlay (also: Alt+Space) |
| Rules | Open the rule manager panel |
| History | Browse execution history |
| Settings | Open the settings dialog |
| Quit | Graceful shutdown |

---

## Settings

Settings are stored in `.env` in the project root.

| Key | Default | Description |
|---|---|---|
| `OLLAMA_MODEL` | `mistral-nemo` | Model to use for inference |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `NUM_CTX` | `4096` | Context window size |
| `OVERLAY_HOTKEY` | `alt+space` | Global hotkey for the overlay |
| `DATA_DIR` | `~/.edgedesk` | Directory for DB and FAISS index |

---

## Development

```bash
# Run all tests
uv run pytest tests/ -v

# Run a single test file
uv run pytest tests/test_agent.py -v

# Coverage report
uv run pytest tests/ --cov=core --cov=tools --cov=db --cov=scheduler --cov-report=term-missing

# Lint + format
uv run ruff format . && uv run ruff check . --fix

# Type check
uv run mypy . --ignore-missing-imports
```

---

## Building a Standalone Executable

```bash
uv run pyinstaller edgedesk.spec
# Output: dist/edgedesk/edgedesk.exe
```

> **Note:** Update `TESSERACT_PATH` in `edgedesk.spec` if Tesseract is not in the default location.

---

## Architecture

```
main.py ──► SystemTrayApp        (ui/tray.py)
         ──► OverlayWindow        (ui/overlay.py)   Alt+Space
         ──► AgentOrchestrator    (core/agent.py)
               ├─ OllamaLLM       (core/llm.py)
               ├─ TOOL_MANIFEST   (tools/*.py)
               └─ MemorySaver     (langgraph)
         ──► SchedulerEngine      (scheduler/engine.py)
         ──► DBSession            (db/session.py → SQLite)
         └─► VectorStore          (db/vector_store.py → FAISS)
```

---

## Model Selection

| VRAM | Auto-selected Model |
|---|---|
| ≥ 8 GB | `mistral-nemo:12b` |
| < 8 GB | `phi3.5:3.8b` |

Override via `OLLAMA_MODEL` in `.env` or the Settings → LLM tab.

---

## Data & Privacy

All data stays on your machine:
- SQLite database: `~/.edgedesk/edgedesk.db`
- FAISS index: `~/.edgedesk/rules.faiss`
- No telemetry, no external API calls in production code.
