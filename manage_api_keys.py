#!/usr/bin/env python3
"""
API Key Management Script for Whale Alert API

This script helps manage and validate existing API keys.

Usage:
    python manage_api_keys.py validate KEY1,KEY2    # Validate specific keys
    python manage_api_keys.py validate --env        # Validate keys from environment
    python manage_api_keys.py list                  # List configured keys (masked)
    python manage_api_keys.py test KEY              # Test key against API
"""

import argparse
import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from api.auth import APIKeyAuth, hash_api_key


def mask_key(key: str, show_chars: int = 8) -> str:
    """Mask an API key for safe display."""
    if len(key) <= show_chars * 2:
        return key[:show_chars//2] + "*" * (len(key) - show_chars) + key[-show_chars//2:]
    return key[:show_chars] + "*" * (len(key) - show_chars * 2) + key[-show_chars:]


def validate_keys(keys: list[str]) -> None:
    """Validate a list of API keys."""
    print(f"Validating {len(keys)} API key{'s' if len(keys) > 1 else ''}...")
    print("=" * 60)
    
    auth = APIKeyAuth()
    
    for i, key in enumerate(keys, 1):
        key = key.strip()
        if not key:
            continue
            
        is_valid = auth.is_valid_api_key(key)
        status = "✅ VALID" if is_valid else "❌ INVALID"
        
        print(f"Key {i}: {mask_key(key)} - {status}")
        
        # Show additional info for valid keys
        if is_valid:
            print(f"  Length: {len(key)} characters")
            if '_' in key:
                prefix = key.split('_')[0]
                print(f"  Prefix: {prefix}")
    
    print("=" * 60)


def list_configured_keys() -> None:
    """List all configured API keys (masked)."""
    try:
        from api.config import api_settings
        keys = [k.strip() for k in api_settings.API_KEYS.split(",") if k.strip()]
        
        print(f"Configured API Keys ({len(keys)} total):")
        print("=" * 50)
        
        for i, key in enumerate(keys, 1):
            print(f"{i}. {mask_key(key)}")
            
        print("=" * 50)
        print(f"Authentication: {'Required' if api_settings.REQUIRE_AUTH else 'Optional'}")
        print(f"Header: {api_settings.API_KEY_HEADER}")
        
    except Exception as e:
        print(f"Error reading configuration: {e}", file=sys.stderr)


def test_key_format(key: str) -> None:
    """Test if a key has the expected format."""
    print(f"Testing key format: {mask_key(key)}")
    print("-" * 40)
    
    # Basic format checks
    checks = [
        ("Length >= 16", len(key) >= 16),
        ("Contains underscore", '_' in key),
        ("Has prefix", key.count('_') >= 1 and len(key.split('_')[0]) > 0),
        ("URL-safe characters", all(c.isalnum() or c in '-_' for c in key)),
    ]
    
    for check_name, passed in checks:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {check_name}: {status}")
    
    # Additional info
    if '_' in key:
        parts = key.split('_')
        print(f"\n  Prefix: {parts[0]}")
        print(f"  Random part length: {len('_'.join(parts[1:]))}")
    
    print(f"  Hash: {hash_api_key(key)}")


def main():
    parser = argparse.ArgumentParser(
        description="Manage API keys for Whale Alert API",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate API keys')
    validate_group = validate_parser.add_mutually_exclusive_group(required=True)
    validate_group.add_argument('keys', nargs='?', help='Comma-separated list of keys to validate')
    validate_group.add_argument('--env', action='store_true', help='Validate keys from environment')
    
    # List command
    subparsers.add_parser('list', help='List configured API keys (masked)')
    
    # Test command
    test_parser = subparsers.add_parser('test', help='Test a single API key')
    test_parser.add_argument('key', help='API key to test')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        if args.command == 'validate':
            if args.env:
                # Get keys from environment
                env_keys = os.getenv('API_KEYS', '')
                if not env_keys:
                    print("No API_KEYS found in environment", file=sys.stderr)
                    sys.exit(1)
                keys = [k.strip() for k in env_keys.split(',') if k.strip()]
            else:
                keys = [k.strip() for k in args.keys.split(',') if k.strip()]
            
            if not keys:
                print("No valid keys provided", file=sys.stderr)
                sys.exit(1)
                
            validate_keys(keys)
            
        elif args.command == 'list':
            list_configured_keys()
            
        elif args.command == 'test':
            test_key_format(args.key)
            
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nOperation cancelled by user", file=sys.stderr)
        sys.exit(1)