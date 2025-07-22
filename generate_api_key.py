#!/usr/bin/env python3
"""
API Key Generator Script for Whale Alert API

This script generates secure API keys that can be used with the Whale Alert API.
Generated keys should be added to the API_KEYS environment variable.

Usage:
    python generate_api_key.py                    # Generate single key with default prefix
    python generate_api_key.py --prefix prod      # Generate with custom prefix
    python generate_api_key.py --count 5          # Generate multiple keys
    python generate_api_key.py --length 40        # Custom key length
    python generate_api_key.py --no-prefix        # Generate without prefix
"""

import argparse
import sys
from pathlib import Path

# Add the project root to Python path to import our modules
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from api.auth import generate_api_key, hash_api_key


def main():
    parser = argparse.ArgumentParser(
        description="Generate secure API keys for Whale Alert API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                           # Generate single key: wha_xxxxx
  %(prog)s --prefix prod             # Generate: prod_xxxxx  
  %(prog)s --count 3                 # Generate 3 keys
  %(prog)s --length 40               # Generate longer key
  %(prog)s --no-prefix               # Generate without prefix
  %(prog)s --show-hash               # Show hash for storage
        """
    )
    
    parser.add_argument(
        "--prefix",
        default="wha",
        help="Prefix for the API key (default: wha)"
    )
    
    parser.add_argument(
        "--no-prefix",
        action="store_true",
        help="Generate API key without prefix"
    )
    
    parser.add_argument(
        "--count",
        type=int,
        default=1,
        help="Number of API keys to generate (default: 1)"
    )
    
    parser.add_argument(
        "--length",
        type=int,
        default=32,
        help="Length of the random part (default: 32)"
    )
    
    parser.add_argument(
        "--show-hash",
        action="store_true",
        help="Also show SHA256 hash of the key (for secure storage)"
    )
    
    parser.add_argument(
        "--format",
        choices=["plain", "json", "env"],
        default="plain",
        help="Output format (default: plain)"
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.count < 1:
        print("Error: --count must be at least 1", file=sys.stderr)
        sys.exit(1)
        
    if args.length < 16:
        print("Error: --length must be at least 16 for security", file=sys.stderr)
        sys.exit(1)
    
    # Generate API keys
    keys = []
    for i in range(args.count):
        if args.no_prefix:
            # Generate key without prefix
            import secrets
            key = secrets.token_urlsafe(args.length)
        else:
            key = generate_api_key(prefix=args.prefix, length=args.length)
        
        key_info = {
            "key": key,
            "hash": hash_api_key(key) if args.show_hash else None
        }
        keys.append(key_info)
    
    # Output based on format
    if args.format == "json":
        import json
        output = {
            "generated_keys": len(keys),
            "keys": [{"api_key": k["key"], "hash": k["hash"]} for k in keys]
        }
        if not args.show_hash:
            for key in output["keys"]:
                del key["hash"]
        print(json.dumps(output, indent=2))
        
    elif args.format == "env":
        key_list = ",".join([k["key"] for k in keys])
        print(f"API_KEYS={key_list}")
        if args.show_hash:
            print("\n# Key hashes for reference:")
            for i, k in enumerate(keys, 1):
                print(f"# Key {i} hash: {k['hash']}")
                
    else:  # plain format
        print(f"Generated {len(keys)} API key{'s' if len(keys) > 1 else ''}:")
        print("=" * 50)
        
        for i, key_info in enumerate(keys, 1):
            print(f"\nKey {i}:")
            print(f"  API Key: {key_info['key']}")
            if args.show_hash:
                print(f"  Hash:    {key_info['hash']}")
        
        print("\n" + "=" * 50)
        print("SECURITY NOTES:")
        print("- Store these keys securely")
        print("- Add to API_KEYS environment variable (comma-separated for multiple)")
        print("- Keys are shown only once - save them now")
        
        if len(keys) > 1:
            all_keys = ",".join([k["key"] for k in keys])
            print(f"\nFor .env file:")
            print(f"API_KEYS={all_keys}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nOperation cancelled by user", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)