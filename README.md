# Whale Alert Record Agent

A Python application that listens to Whale Alert messages on Telegram, processes them using LLM, and stores structured data in TimescaleDB for analysis.

## 🚀 Features

- 📡 Listens to Whale Alert messages using Telethon
- 🗄️ Processes and structures messages using LLM (GPT-4o)
- 🗃️ Stores structured data in TimescaleDB for time-series analysis
- 🐳 Docker support for easy deployment
- ⚡ Asynchronous processing for better performance
- 🔄 Automatic hash collision handling
- 📊 Ready for data analysis and visualization

## 📋 Prerequisites

- Docker and Docker Compose
- Python 3.11+ (for development)
- OpenAI API key (for LLM processing)
- Telegram API credentials

## 🚀 Quick Start with Docker

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/whale-alert-record-agent.git
   cd whale-alert-record-agent
   ```

2. Copy the example environment file and update with your credentials:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and fill in your API keys and configuration.

3. Build the Docker image:
   ```bash
   ./docker-build.sh
   ```

4. Step 1: Generate Telegram session
   First, create a sessions directory and set the correct ownership:
   ```bash
   mkdir -p sessions
   sudo chown -R 1000:1000 sessions  # Set owner to match the container user
   ```
   
   Then run the session generation:
   ```bash
   docker run --rm -it \
     --name whale-alert-session \
     -e TZ=UTC \
     -v "$(pwd)/.env:/app/.env" \
     -v "$(pwd)/sessions:/app/sessions" \
     --network whale-alert-net \
     whale-alert:latest \
     python generate_tg_session.py
   ```

5. Step 2: Start the application with Docker Compose:
   ```bash
   docker-compose up -d
   ```

6. View logs:
   ```bash
   docker-compose logs -f
   ```

## ⚙️ Configuration

Edit the `.env` file with your configuration:

```env
# Telegram API credentials (get from https://my.telegram.org/apps)
API_ID=your_api_id_here
API_HASH=your_api_hash_here
PHONE_NUMBER=your_phone_number_with_country_code  # e.g., +1234567890
CHANNEL_USERNAME=whale_alert

# Database connection
TIMESCALEDB_URL=postgresql://postgres:postgres@timescaledb:5432/whale_alert

# OpenAI API Key (required for LLM parsing)
OPENAI_API_KEY=your_openai_api_key_here

# LLM Settings
LLM_MODEL=gpt-4o  # or gpt-3.5-turbo for faster/cheaper parsing
LLM_TEMPERATURE=0.0  # 0.0 for deterministic output

# Application settings
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
```

## 🛠 Development

### Local Setup

1. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: .\venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   uv pip install -r requirements.txt
   ```

3. Run the application:
   ```bash
   python -m whale_alert
   ```

### Development Commands

- Format code: `uv run format`
- Lint code: `uv run lint`
- Run tests: `uv run test`
- Start development server: `uv run dev`

## 📊 Database Schema

The application uses TimescaleDB (PostgreSQL) with the following main tables:

- `whale_alerts`: Stores processed whale alert data

## 🔄 Deployment

For production deployment, consider:

1. Using a managed database service
2. Setting up proper backups
3. Configuring monitoring and alerting
4. Using environment variables for sensitive data

## 🤝 Contributing

Contributions are welcome! Please read our [Contributing Guidelines](CONTRIBUTING.md) for details.

## 📄 License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Whale Alert](https://whale-alert.io/) for the data
- [Telegram](https://telegram.org/) for the messaging platform
- [OpenAI](https://openai.com/) for the LLM processing
- [TimescaleDB](https://www.timescale.com/) for time-series data storage
