<p align="center">
  <img src="image.png" alt="Punch.io Mascot" width="150">
</p>

<h1 align="center">🔬 Punch.io</h1>
<p align="center"><strong>Project Communication Intelligence</strong></p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.14+-blue?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/LangChain-RAG-green?style=for-the-badge" alt="LangChain">
  <img src="https://img.shields.io/badge/Streamlit-Frontend-red?style=for-the-badge&logo=streamlit&logoColor=white" alt="Streamlit">
  <img src="https://img.shields.io/badge/FAISS-Vector%20DB-yellow?style=for-the-badge" alt="FAISS">
</p>

---

**Punch.io** is a Retrieval-Augmented Generation (RAG) application that transforms your team's scattered project communications into an intelligent, searchable knowledge base. Ask natural language questions about your project and get accurate, context-aware answers sourced directly from your Discord channels.

Built for teams managing complex technical projects where critical decisions, context, and institutional knowledge are often buried in chat histories.

---

## ✨ Features

- **🤖 AI-Powered Q&A** — Ask questions in plain English and receive accurate answers grounded in your actual project communications
- **🔍 Semantic Search** — FAISS vector database enables lightning-fast similarity search across thousands of messages
- **📥 Live Discord Sync** — One-click synchronization pulls the latest messages from your Discord channels
- **💬 Chat Interface** — Beautiful Streamlit-powered web UI with conversation history
- **📄 Source Attribution** — Every answer includes expandable context showing exactly which messages informed the response
- **⚡ Groq LLM Integration** — Powered by Llama 3.3 70B via Groq for blazing-fast inference
- **🧩 Modular Architecture** — Clean separation of concerns: fetching, processing, generation, and presentation

---

## 🏗️ Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Data Sources  │ ──▶ │  Vector Database │ ──▶ │   LLM + RAG     │
│   (Discord)     │     │     (FAISS)      │     │   (Groq API)    │
└─────────────────┘     └──────────────────┘     └─────────────────┘
         │                       │                        │
         ▼                       ▼                        ▼
   fetcher/              processing/               generation/
   └── fetch_discord.py  └── build_vector_db.py   └── llm.py
                                                          │
                                                          ▼
                                                  ┌───────────────┐
                                                  │   Streamlit   │
                                                  │    Web App    │
                                                  └───────────────┘
```

---

## 📋 Prerequisites

- **Python 3.14+**
- **[uv](https://docs.astral.sh/uv/)** — Fast Python package manager (recommended)
- **Groq API Key** — Free tier available at [console.groq.com](https://console.groq.com)
- **Discord Bot Token** — For fetching channel messages

---

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/punch.io.git
cd punch.io
```

### 2. Install Dependencies

```bash
uv sync
```

### 3. Configure Environment Variables

Create a `.env` file in the project root:

```env
GROQ_API_KEY=gsk_your_groq_api_key_here
DISCORD_BOT_TOKEN=your_discord_bot_token_here
DISCORD_CHANNEL_ID=your_channel_id_here
```

> 📖 See [Discord Bot Setup](#-discord-bot-setup) below for detailed instructions.

### 4. Fetch Initial Data & Build Vector Database

```bash
uv run python -m fetcher.fetch_discord
uv run python -m processing.build_vector_db
```

### 5. Launch the Application

```bash
uv run streamlit run app.py
```

Open your browser at `http://localhost:8501`.

---

## 🤖 Discord Bot Setup

### Step 1: Create a Discord Application

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications)
2. Click **New Application** and give it a name
3. Click **Create**

### Step 2: Create the Bot & Get Token

1. In the left sidebar, click **Bot**
2. Click **Reset Token** and copy it immediately
3. Save this as `DISCORD_BOT_TOKEN` in your `.env` file

### Step 3: Enable Message Content Intent (CRITICAL ⚠️)

> **Without this step, the bot will connect but return EMPTY messages!**

Discord requires explicit approval for bots to read message text. This is a privacy protection.

1. On the **Bot** page, scroll to **Privileged Gateway Intents**
2. Enable **Message Content Intent** (toggle it ON - it should turn green)
3. Click **Save Changes**

If you skip this step, `fetch_discord.py` will return 0 messages even though the bot is connected.

### Step 4: Invite the Bot to Your Server

1. Go to **OAuth2** → **URL Generator**
2. Check `bot` under **Scopes**
3. Check `Read Messages/View Channels` and `Read Message History` under **Bot Permissions**
4. Copy the generated URL, paste it in your browser, and authorize

### Step 5: Get the Channel ID

1. In Discord, enable **Developer Mode** (User Settings → Advanced)
2. Right-click your channel → **Copy Channel ID**
3. Save as `DISCORD_CHANNEL_ID` in your `.env` file

---

## 📁 Project Structure

```
punch.io/
├── app.py                      # Streamlit web application
├── pyproject.toml              # Project configuration
├── .env                        # Environment variables (not in git)
│
├── fetcher/                    # Data ingestion module
│   ├── __init__.py
│   └── fetch_discord.py
│
├── processing/                 # Data processing module
│   ├── __init__.py
│   └── build_vector_db.py
│
├── generation/                 # LLM & RAG module
│   ├── __init__.py
│   └── llm.py
│
└── data/                       # Generated data (not in git)
    ├── discord_chat.json
    └── faiss_db/
```

---

## 🖥️ Usage

### Web Interface

1. Launch the app: `uv run streamlit run app.py`
2. Use the **📥 Fetch Latest Discord Messages** button in the sidebar to sync new messages
3. Type your question in the chat input
4. View the AI's response along with the source messages it used

### Command Line

```bash
# Interactive Q&A in terminal
uv run python -m generation.llm

# Fetch latest Discord messages
uv run python -m fetcher.fetch_discord

# Rebuild vector database
uv run python -m processing.build_vector_db
```

---

## 🌐 Deployment

### Streamlit Cloud (Recommended)

1. Push your code to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your repository
4. Add your secrets in the dashboard:
   ```toml
   GROQ_API_KEY = "gsk_..."
   DISCORD_BOT_TOKEN = "..."
   DISCORD_CHANNEL_ID = "..."
   ```
5. Deploy!

### Docker

```dockerfile
FROM python:3.14-slim
WORKDIR /app
COPY . .
RUN pip install uv && uv sync
EXPOSE 8501
CMD ["uv", "run", "streamlit", "run", "app.py", "--server.address", "0.0.0.0"]
```

```bash
docker build -t punch-io .
docker run -p 8501:8501 --env-file .env punch-io
```

---

## 🔧 Configuration

| Variable | Description | Required |
|----------|-------------|----------|
| `GROQ_API_KEY` | API key from [Groq Console](https://console.groq.com) | Yes |
| `DISCORD_BOT_TOKEN` | Discord bot token | Yes |
| `DISCORD_CHANNEL_ID` | Discord channel to monitor | Yes |

---

## 📄 License

MIT License

---

<p align="center">
  Built with ❤️ for teams who hate losing context
</p>
