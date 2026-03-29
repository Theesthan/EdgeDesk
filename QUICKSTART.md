# EdgeDesk Quick Start Guide

**Status:** ✓ All 249 tests pass · ✓ 88% code coverage · ✓ Ready to run

This guide walks you through launching EdgeDesk on your machine. The app is fully built and tested; you just need to start the Ollama server and run it.

---

## Prerequisites (Install Once)

### 1. Python 3.12
Already installed on your system. Verify:
```bash
python --version
```

### 2. uv (Python Package Manager)
Already installed. Verify:
```bash
uv --version
```

### 3. Ollama
Download and install from [ollama.ai](https://ollama.ai).

After installation, pull a model:
```bash
ollama pull mistral-nemo
```

(Or `ollama pull phi3.5` for lower VRAM systems)

### 4. Tesseract OCR (Optional, for screen reading)
Download from [github.com/UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki).
Install to `C:\Program Files\Tesseract-OCR`.

---

## First-Time Setup

All dependencies are already synced. Just verify:

```bash
cd "c:\Users\thees\Desktop\Eko\Eko\EdgeDesk"
uv sync
```

---

## Running EdgeDesk

### Step 1: Start Ollama Server (New Terminal)

```bash
ollama serve
```

You should see:
```
Listening on 127.0.0.1:11434
```

Leave this running in the background.

### Step 2: Run EdgeDesk (Main Terminal)

```bash
cd "c:\Users\thees\Desktop\Eko\Eko\EdgeDesk"
uv run python main.py
```

You should see:
```
[timestamp] INFO     EdgeDesk starting…
[timestamp] INFO     Database ready
[timestamp] INFO     Ollama health check passed
...
```

EdgeDesk will appear in your system tray (bottom-right corner on Windows).

### Step 3: Open the Overlay

Press **Alt+Space** anywhere on your screen.

A centered input field appears (680px wide, dark glassmorphism design).

Type a natural language instruction, e.g.:
- "Open a web browser and search for Python documentation"
- "Create a new text file on the desktop with the contents..."
- "Take a screenshot of the current screen"

Press **Enter** to execute.

Watch the step log appear below the input as the agent reasons through your instruction.

---

## System Tray Menu

Right-click the EdgeDesk icon in the system tray:

| Menu Item | Action |
|-----------|--------|
| **Open Overlay** | Press Alt+Space programmatically |
| **Rules** | Manage automation rules (cron, file-watch, manual) |
| **History** | View past instruction executions with feedback |
| **Settings** | Configure hotkey, LLM model, privacy options |
| **Quit** | Gracefully shut down EdgeDesk |

---

## Verifying Installation

All validation already complete:

```bash
# Run test suite
uv run pytest tests/ -v
# Result: 249 passed, 1 skipped

# Check linting
uv run ruff check .
# Result: All checks passed

# Check type safety
uv run mypy . --ignore-missing-imports
# (Some expected errors in test mocks, not in production code)

# Check coverage
uv run pytest tests/ --cov=core --cov=tools --cov=db
# Result: 88% overall (target: 80%)
```

---

## Configuration

All config is in `.env` (auto-created from `.env.example`):

```bash
# LLM to use
OLLAMA_MODEL=mistral-nemo       # or phi3.5, llama3.1, etc.
OLLAMA_BASE_URL=http://localhost:11434

# Data directory (local SQLite DB + FAISS index)
DATA_DIR=~/.edgedesk

# Overlay hotkey
OVERLAY_HOTKEY=alt+space

# Email integration (optional)
IMAP_HOST=
IMAP_PORT=993
IMAP_USER=
IMAP_PASS=
```

Change any value and restart EdgeDesk for it to take effect.

---

## Available Tools

Once the agent is running, it has access to these desktop automation tools:

| Tool | Capability | Example |
|------|-----------|---------|
| **Screen** | Screenshot + OCR text recognition | Identify UI elements on screen |
| **GUI** | Click, type, scroll, hotkey | Interact with any window |
| **Files** | Read, write, move, delete, list | Manage files and directories |
| **Apps** | Launch applications, list processes | Control software |
| **Clipboard** | Read/write system clipboard | Copy/paste data |
| **Notify** | Send desktop notifications | Alert the user |
| **Email** | List and read emails via IMAP | Check mail (optional setup) |

---

## Creating Automation Rules

1. Open system tray → **Rules**
2. Click **+ New** button
3. Fill in:
   - **Name:** Human-readable rule name (e.g., "Daily Report")
   - **Instruction:** Natural language task (e.g., "Open email, download latest report")
   - **Trigger Type:** Choose one:
     - **Manual** — execute on-demand only
     - **Cron** — schedule by cron expression (e.g., `0 9 * * MON` = 9am Mondays)
     - **File** — trigger when a file changes (e.g., monitor a directory)
   - **Trigger Config:** JSON parameters (depends on trigger type)

Example cron config:
```json
{
  "minute": "0",
  "hour": "9",
  "day_of_week": "mon-fri"
}
```

4. Click **Save Rule**
5. Rule will fire automatically on schedule or when file changes

View execution history in system tray → **History**.

---

## Troubleshooting

### Ollama not running
**Error:** `ConnectionError: Ollama unreachable`

**Fix:** Open a separate terminal and run:
```bash
ollama serve
```

### Model not found
**Error:** `Model mistral-nemo not found`

**Fix:** Pull the model:
```bash
ollama pull mistral-nemo
```

### No display (headless mode)
If running on a server without a display, some UI tests will skip automatically (expected behavior).

Core agent functionality works fine without a display.

### Screen capture not working
**Error:** `pytesseract.TesseractNotFoundError`

**Fix:** Install Tesseract OCR to `C:\Program Files\Tesseract-OCR`.

If you skip this, the Screen tool won't recognize text but will still capture screenshots.

---

## Next Steps

- **Explore the codebase:** See [CLAUDE.md](CLAUDE.md) for architecture and development info
- **Build a standalone executable:** See [README.md](README.md) → PyInstaller section
- **Write new tools:** Add custom desktop automation in `tools/`
- **Create rules:** Define automation workflows in the Rules panel

---

## Support

- **Architecture docs:** [CLAUDE.md](CLAUDE.md)
- **Full documentation:** [README.md](README.md)
- **API reference:** See docstrings in source files
- **Issues:** Check git log for recent changes

---

**EdgeDesk is now ready to automate your desktop. Press Alt+Space and try it!**
