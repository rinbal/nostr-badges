#!/usr/bin/env python3
"""
Badge Acceptance Tool
Allows recipients to accept and display badges in their profile
"""

import json
import asyncio
import sys
from pathlib import Path
from recipient_acceptance import BadgeAcceptanceManager


def load_config():
    """Load configuration from config.json"""
    try:
        with open("config.json", "r") as f:
            return json.load(f)
    except:
        return {
            "relay_urls": [
                "wss://relay.damus.io",
                "wss://nos.lol",
                "wss://nostr.wine",
                "wss://offchain.pub",
                "wss://relay.snort.social",
                "wss://relay.primal.net",
                "wss://relay.nostr.band"
            ]
        }


def get_recipient_key():
    """Get recipient private key"""
    while True:
        nsec = input("Enter your private key (nsec): ").strip()
        if nsec.startswith("nsec1"):
            return nsec
        else:
            print("❌ Invalid format. Must start with 'nsec1'")


def get_badge_info():
    """Get badge information from user"""
    print("\n📋 Enter badge information:")
    
    badge_definition_a_tag = input("Badge Definition A-tag (e.g., 30009:pubkey:identifier): ").strip()
    if not badge_definition_a_tag.startswith("30009:"):
        print("❌ Invalid A-tag format. Must start with '30009:'")
        return None, None
    
    badge_award_event_id = input("Badge Award Event ID (64-char hex): ").strip()
    if len(badge_award_event_id) != 64 or not all(c in "0123456789abcdef" for c in badge_award_event_id.lower()):
        print("❌ Invalid Event ID format. Must be 64-char hex")
        return None, None
    
    return badge_definition_a_tag, badge_award_event_id


async def accept_badge_interactive():
    """Interactive badge acceptance flow"""
    print("🏅 Nostr Badge Acceptance Tool")
    print("=" * 50)
    
    # Load configuration
    config = load_config()
    relay_urls = config.get("relay_urls", [])
    print(f"📡 Using {len(relay_urls)} relays")
    
    # Get recipient key
    recipient_nsec = get_recipient_key()
    acceptance_manager = BadgeAcceptanceManager(recipient_nsec)
    recipient_info = acceptance_manager.get_recipient_info()
    print(f"👤 Recipient: {recipient_info['npub']}")
    
    # Get badge information
    badge_definition_a_tag, badge_award_event_id = get_badge_info()
    if not badge_definition_a_tag or not badge_award_event_id:
        print("❌ Invalid badge information")
        return
    
    print(f"\n🎯 Ready to accept badge:")
    print(f"   Badge Definition: {badge_definition_a_tag}")
    print(f"   Award Event ID: {badge_award_event_id}")
    
    # Show options
    print(f"\n🔧 Choose acceptance method:")
    print("1) Auto-accept (create and publish Profile Badges event)")
    print("2) Manual instructions (copy/paste JSON)")
    print("3) Exit")
    
    choice = input("Select option (1-3): ").strip()
    
    if choice == "1":
        # Auto-accept
        confirm = input("\nProceed to accept and display this badge? (y/n): ").lower()
        if confirm == "y":
            result = await acceptance_manager.accept_badge(
                badge_definition_a_tag, badge_award_event_id, relay_urls
            )
            
            if result["status"] == "success":
                print(f"\n🎉 BADGE ACCEPTED SUCCESSFULLY!")
                print(f"Profile Badges Event ID: {result['event']['id']}")
                print("The badge should now be visible in your profile!")
            else:
                print(f"\n⚠️ Badge accepted but not yet verified")
                print("It may take a few minutes to appear in your profile.")
        else:
            print("❌ Cancelled")
    
    elif choice == "2":
        # Manual instructions
        instructions = await acceptance_manager.generate_manual_instructions(
            badge_definition_a_tag, badge_award_event_id, relay_urls, relay_urls[0] if relay_urls else None
        )
        print(instructions)
        
        # Save instructions to file
        instructions_file = Path("badge_acceptance_instructions.txt")
        with open(instructions_file, "w", encoding="utf-8") as f:
            f.write(instructions)
        print(f"\n💾 Instructions saved to: {instructions_file}")
    
    elif choice == "3":
        print("👋 Goodbye!")
    
    else:
        print("❌ Invalid option")


async def accept_badge_from_args():
    """Accept badge from command line arguments"""
    if len(sys.argv) < 4:
        print("Usage: python3 accept_badge.py <nsec> <badge_definition_a_tag> <badge_award_event_id>")
        print("\nExample:")
        print("python3 accept_badge.py nsec1... 30009:pubkey:identifier event_id_here")
        sys.exit(1)
    
    recipient_nsec = sys.argv[1]
    badge_definition_a_tag = sys.argv[2]
    badge_award_event_id = sys.argv[3]
    
    print("🏅 Auto-accepting badge...")
    
    # Load configuration
    config = load_config()
    relay_urls = config.get("relay_urls", [])
    
    # Initialize acceptance manager
    acceptance_manager = BadgeAcceptanceManager(recipient_nsec)
    recipient_info = acceptance_manager.get_recipient_info()
    print(f"👤 Recipient: {recipient_info['npub']}")
    
    # Accept badge
    result = await acceptance_manager.accept_badge(
        badge_definition_a_tag, badge_award_event_id, relay_urls
    )
    
    if result["status"] == "success":
        print(f"🎉 BADGE ACCEPTED SUCCESSFULLY!")
        print(f"Profile Badges Event ID: {result['event']['id']}")
        print("The badge should now be visible in your profile!")
    else:
        print(f"⚠️ Badge accepted but not yet verified")
        print("It may take a few minutes to appear in your profile.")


if __name__ == "__main__":
    try:
        if len(sys.argv) > 1:
            # Command line mode
            asyncio.run(accept_badge_from_args())
        else:
            # Interactive mode
            asyncio.run(accept_badge_interactive())
    except KeyboardInterrupt:
        print("\n❌ Cancelled by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
