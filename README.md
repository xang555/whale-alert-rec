# Whale Alert Record Agent

A Python application that listens to Whale Alert messages on Telegram, processes them using LLM, and stores structured data in TimescaleDB for analysis.

## Features

- Listens to Whale Alert messages using Telethon
- Stores messages in TimescaleDB for time-series analysis
- Configurable through environment variables
- Asynchronous processing for better performance

## Prerequisites

- Python 3.8+
- TimescaleDB (can be run via Docker)
- Telegram API credentials

## Installation

1. Clone the repository
2. Install dependencies using `uv`:
   ```bash
   uv pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and fill in your credentials
4. Run the application:
   ```bash
   python -m whale_alert
   ```

## Configuration

Copy `.env.example` to `.env` and update the following variables:

```env
# Telegram API credentials
API_ID=your_api_id
API_HASH=your_api_hash
PHONE_NUMBER=your_phone_number
CHANNEL_USERNAME=whale_alert

# TimescaleDB connection
TIMESCALEDB_URL=postgresql://user:password@localhost:5432/whale_alert
```

## Development

- Format code: `uv run format`
- Lint code: `uv run lint`
- Run tests: `uv run test`

## License

MIT
