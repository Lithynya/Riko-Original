# 🧠 MCP Servers for the RIKO Project

This repository contains the **MCP (Model Context Protocol)** servers and tools that extend the **RIKO Project**, enabling Riko to communicate with:

* 🌐 External services — Discord, Gmail, Twitter, etc.
* 🧍 Local tools — lipsync, VRM animation, and Python code execution

Each MCP server is modular and self-contained, allowing Riko to connect and interact dynamically with multiple systems.

---

## ⚙️ Requirements

Before getting started, make sure you have:

* 🐍 **Python 3.10+**
* 🧰 A virtual environment (`python -m venv .venv`)
* 🚀 The **Riko Project** installed and configured
* 🌍 An **ngrok** account (for exposing local MCP servers)
* 🔑 API keys in a `.env` file, for example:

```bash
OPENAI_API_KEY=""
```

---

## 🚀 Quickstart

### 1️⃣ Setup your environment

```bash
python -m venv .venv
.venv\Scripts\activate   # on Windows
source .venv/bin/activate  # on Linux/Mac

pip install uv
pip install -r requirements.txt
```

---

### 2️⃣ Configure paths

Locate your Riko project directory (for example):

```
D:\PyProjects\waifu_project\riko_project_MCP
```

Then edit `riko_project_mcp_config.yaml` at the root of the riko project:

```yaml
riko_project_mcp_location: D:\PyProjects\waifu_project\riko_project_MCP
```

This tells all MCP tools where your main Riko MCP folder lives.
Each server will read this to locate `mcp_config.json`.

---

### 3️⃣ Directory layout example

```
riko_project_mcp/
│
├── riko_project_mcp_config.yaml
│
├── DiceCaller/
│   └── dice_server.py
│
├── DiscordBot/
│   └── discord_bridge.py
│
└── GmailSender/
    └── gmail_server.py
```

Each folder (`DiceCaller`, `DiscordBot`, etc.) is a **server** —
the folder name automatically becomes the **server name** and **audience** for JWT authentication.

---

## 🧩 MCP Tool Types

Each tool inside a server must declare its type:

| Type          | Description                                                                        |
| ------------- | ---------------------------------------------------------------------------------- |
| **need_sync** | Tools that run in sync with Riko’s dialogue or playback                            |
| **can_async** | Tools that can run freely in the background                                        |
| **long_task** | Tools that trigger longer background processes and return a “task started” message |

This classification helps Riko decide **when** and **how** to execute tools efficiently.

---

## 🧪 Running a Test Server

1. Launch the example Dice MCP server:

   ```bash
   cd DiceCaller
   python dice_server.py
   ```

2. Launch the manual MCP test:

   ```bash
   python manual_mcp_call.py
   ```

If everything is connected correctly, you should see:

```
Result: {
  'content': [{'type': 'text', 'text': '[2,3,5]'}],
  'structuredContent': {'result': [2, 3, 5]},
  'isError': False
}
```

---

## 🔗 Integrating with Riko

Once your MCP servers are running:

1. Launch your MCP server(s) first (e.g. `DiceCaller/dice_server.py`)
2. Run Riko’s startup script:

   ```bash
   start_servers.bat
   ```
3. Then start Riko’s main system:

   ```bash
   python main_chat_stream_tools.py
   ```

This will connect Riko to all active MCP servers and enable tool calls in real-time.

---

## 📜 Notes

* Each MCP server automatically creates and stores its credentials under:

  ```
  ~/riko_project_mcp/<server_name>/mcp_config.json
  ```
* Cross-platform compatible with **Windows**, **Linux**, and **WSL2**
* Uses **ngrok** for public tunneling (optional, configurable in YAML)

---

## 🪪 License

This project is currently **private** and not for redistribution.
It will be made public at a later date.
Please **do not share** this repository or any of its contents until then.