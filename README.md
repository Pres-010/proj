# Sisky AI Project

A simple Python CLI agent for entrepreneurs in Kigali with:
- Login and registration
- Conversation history with delete support
- Settings section for language, theme, and Google Search toggle
- Payment plans: `basic`, `pro`, `promax`

## Run locally

1. Install Python 3.11+
2. Run `python main.py`
3. Use the menu to register, login, chat, manage history, change settings, and select a plan.

## Optional Google Search

If you want live search support, set `GOOGLE_API_KEY` in `config.py` or an environment variable.

## Files

- `main.py` — main CLI application
- `database_setup.py` — SQLite database setup and persistence
- `config.py` — optional Google API configuration
- `Dockerfile` — optional container entrypoint
- `docker-compose.yml` — optional compose service
