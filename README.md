# Nyx - Discord Bot

A modular Discord moderation and utility bot built with discord.py. Comes with reaction roles, sticky messages, auto-threading, and a full suite of moderation commands.

## Technologies Used

- `Python 3`
- `discord.py`
- `aiosqlite`
- `python-dotenv`

## Features

Here's what you can do with this bot:

- **Moderation Commands**: Purge messages, unban members, and bulk-delete channels.

- **Reaction Role Panels**: Build interactive role selection panels with a setup wizard. Choose a title, description, color, and pick roles. Users can self-assign or remove roles through a dropdown menu. Panels persist across bot restarts.

- **Sticky Messages**: Pin a message to the bottom of a channel. Every time someone sends a new message, the sticky is automatically re-posted as the latest message, keeping important info always visible.

- **Auto-Threading**: Automatically create a thread for every new message in configured channels. Threads are named after the message content and archive after 24 hours.

## What I Learned

### Discord Bot Architecture

- **Cogs**: Organizing bot functionality into modular cogs for moderation, roles, sticky messages, and auto-threading.
- **Slash Commands**: Using discord.py's `app_commands` framework for modern Discord slash commands with type hints.
- **Persistent Views**: Implementing `discord.ui.View` with `timeout=None` for reaction role panels that survive bot restarts.

### Database with aiosqlite

- **Async SQLite**: Using `aiosqlite` for non-blocking database operations within an async bot.
- **Schema Design**: Managing multiple feature tables (reaction_roles, stickies, autothread) in a single database file.

### UI Components

- **Modals**: Collecting user input through Discord modals for panel descriptions and sticky message content.
- **Select Menus**: Building dynamic dropdown menus for channel picking, role selection, and toggle-based role assignment.
- **Interactive Wizards**: Multi-step setup flows using views, buttons, and modals for creating reaction role panels.

## Running the Project

To run the project in your local environment, follow these steps:

1. Clone the repository to your local machine.
2. Copy `.env.example` to `.env` and fill in your bot token.
3. Run `pip install -r requirements.txt` to install the required dependencies.
4. Run `python main.py` to start the bot.
