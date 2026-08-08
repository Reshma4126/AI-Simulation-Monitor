# CPR Debriefing System — Deployment Guide

> **For the client receiving this package**

---

## What You Need (One-Time Setup)

Install **Docker Desktop** — this is the only thing you need to install.

👉 Download: https://www.docker.com/products/docker-desktop/

- Windows 10/11 (64-bit) required
- Enable WSL2 when prompted during installation
- After installing, launch Docker Desktop and wait until it shows **"Docker Desktop is running"** in the system tray

---

## How to Run the App

1. **Unzip** the project folder anywhere on your PC (e.g. `C:\cpr_debriefing\`)

2. **Double-click `run.bat`**

   The script will:
   - ✅ Check Docker is running
   - ✅ Detect your GPU automatically (uses GPU if available, CPU otherwise)
   - ✅ Download the AI model on first run (~400 MB, one time only)
   - ✅ Build and start the app
   - ✅ Open your browser at **http://localhost:5000**

> ⏳ **First launch takes 5–10 minutes** (downloads the AI model).  
> Every launch after that is fast (~30 seconds).

---

## How to Stop the App

Double-click **`stop.bat`**

Your reports and uploaded files are always preserved between restarts.

---

## Configuration (Optional)

If you need to change settings, open the **`.env`** file in a text editor.

| Setting | Default | When to change |
|---|---|---|
| `OLLAMA_MODEL` | `qwen2.5:0.5b` | Want better AI quality (use `qwen2.5:3b`) |
| `HF_TOKEN` | *(blank)* | Only if using live audio upload |
| `ANTHROPIC_API_KEY` | *(blank)* | Only if switching to Claude narratives |

---

## Troubleshooting

**"Docker is not running"**  
→ Open Docker Desktop from the Start Menu and wait for it to fully start.

**App doesn't open after 10 minutes**  
→ Open a terminal and run: `docker compose logs app`  
→ Share the output for support.

**Port 5000 already in use**  
→ Change the port in `docker-compose.yml`: `"5001:5000"` → access at http://localhost:5001

**Reset everything (clean start)**  
```
docker compose down -v
```
⚠️ This deletes all saved reports and uploads.

---

## What's Running Inside Docker

```
Your Browser
    │
    ▼
http://localhost:5000
    │
    ├── Flask App (server.py)
    │     └── Serves the React UI + REST API
    │
    └── Ollama (LLM server)
          └── qwen2.5:0.5b  ← generates narrative reports locally
```

All AI processing happens **locally on your machine** — no data is sent to the internet.
