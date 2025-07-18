#!/usr/bin/env python3
"""
Script to generate and save a Telegram session file.
This will prompt for your phone number and OTP.
"""
import asyncio
import os
from whale_alert.telegram.client import WhaleAlertClient
from whale_alert.config import settings

async def generate_session():
    """Generate and save a Telegram session file."""
    print("Initializing Telegram client...")
    client = WhaleAlertClient()
    
    # Ensure the sessions directory exists
    os.makedirs('sessions', exist_ok=True)
    
    try:
        print("Starting Telegram client...")
        print("You'll be prompted for your phone number and OTP.")
        
        # Start the client and handle the authentication
        await client.client.start(phone=settings.PHONE_NUMBER)
        
        # Get the session file path
        session_path = os.path.abspath(os.path.join('sessions', f"{settings.SESSION_NAME}.session"))
        print(f"\nSession successfully created and saved to: {session_path}")
        
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        # Ensure the client is properly disconnected
        if client.client.is_connected():
            await client.client.disconnect()
        print("Done.")

if __name__ == "__main__":
    asyncio.run(generate_session())
