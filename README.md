# AchieveItTogether Bot

**AchieveItTogether** is a powerful, interactive Discord bot designed to help communities and individuals track their goals, reach milestones, and stay consistent with customizable reminders. 

Whether your server is tracking daily steps, reading books, or learning new skills, this bot seamlessly integrates into your chat to keep everyone motivated.

## Key Features

* **Lightning-Fast Progress Tracking**: Log your progress via slash commands (`/add`) or naturally in the chat using quick text commands (e.g., `$steps 5000` or `$books 1 @User`).
* **Milestones**: Automatically detects and celebrates when users reach predefined milestones.
* **Smart Reminders (UI)**: Features an intuitive, interactive UI (Dropdowns & Modals) for setting up recurring DM reminders for specific days of the week.
* **Multi-language Support (i18n)**: Fully supports English and partially Polish out of the box. The bot automatically detects the user's Discord app language for slash commands!
* **Highly Optimized**: Uses a fast in-memory Lazy Loading Cache (`services/cache.py`) to minimize database queries while reading chat messages.
* **Docker Ready**: Easily deployable using the provided `Dockerfile` and `docker-compose.yml`.

## Tech Stack

* **Language**: Python 3.14
* **Framework**: [Discord.py](https://github.com/Rapptz/discord.py)
* **Database**: PostgreSQL with SQLAlchemy (Async)
* **Deployment**: Docker & Docker Compose

## Commands Overview

### Slash Commands
* `/create <name>` - Create a new goal on the server (locks it to the current channel).
* `/add <goal> <amount> [@user]` - Add progress to a specific goal.
* `/notify <goal>` - Opens an interactive menu to set up DM reminders for a goal.
* `/milestone <goal>` - Adds a milestone to a goal using a form.
* `/lock_channel` - Locks a goal to the current channel.
* `/unlock_channel` - Unlock a goal (make it available in all channels).
* `/help` - Displays the help menu with a list of currently active goals.

### Quick Chat Command
Typing directly in the chat is the fastest way to log progress!
* `$<goal> <amount> [@user]` - Logs progress for yourself (e.g., `$pushups 50`) or someone else.

## Installation & Setup

The recommended way to run the bot is via Docker.

### 1. Clone the repository
```bash
git clone https://github.com/Donkrzawayan/AchiveItTogether.git
cd AchiveItTogether
```

### 2. Configure Environment Variables
Create a .env file in the root directory.
```ini
# Discord Configuration
DISCORD_TOKEN=discord_bot_token
ALLOWED_ROLE_ID=123456789012345678 # ID of the role allowed to manage locking goals to channels

# Database Configuration
POSTGRES_USER=postgres
POSTGRES_PASSWORD=secure_password
POSTGRES_DB=achive_db
POSTGRES_HOST=db
POSTGRES_PORT=5432
```

### 3. Run with Docker
Build and start the containers (Bot + Database).
```bash
docker-compose up -d --build
```
