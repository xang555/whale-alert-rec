#!/bin/bash

# Create sessions directory if it doesn't exist
mkdir -p sessions

# Run the session generation script in the container
docker run --rm -it \
  --name whale-alert-session \
  -e TZ=UTC \
  -v "$(pwd)/.env:/app/.env" \
  -v "$(pwd)/sessions:/app/sessions" \
  --network whale-alert-net \
  whale-alert:latest \
  python generate_tg_session.py

# Set proper permissions for the session file
chmod 600 sessions/*.session 2>/dev/null || true

echo "\nSession generation complete. Check the 'sessions' directory for your session file."
