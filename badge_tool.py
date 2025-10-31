#!/usr/bin/env python3
"""
Nostr Badge Tool, main
"""

import json
import asyncio
import sys
from pathlib import Path
from badge_creator import BadgeCreator, normalize_pubkey, normalize_pubkey_to_npub
from recipient_acceptance import BadgeAcceptanceManager
from relay_manager import RelayManager


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


def load_badge_definitions():
    """Load badge definitions from JSON files"""
    definitions_dir = Path("badges/definitions")
    badges = {}
    
    for file in definitions_dir.glob("*.json"):
        try:
            with open(file, "r") as f:
                data = json.load(f)
                # Extract identifier from 'd' tag
                identifier = next((tag[1] for tag in data["tags"] if tag[0] == "d"), file.stem)
                badges[identifier] = data
        except Exception as e:
            print(f"⚠️ Error loading {file}: {e}")
    
    return badges


def display_badges(badges):
    """Display available badges"""
    print("\n📋 Available Badges:")
    print("-" * 50)
    
    for i, (identifier, badge) in enumerate(badges.items(), 1):
        name = next((tag[1] for tag in badge["tags"] if tag[0] == "name"), identifier)
        description = next((tag[1] for tag in badge["tags"] if tag[0] == "description"), "No description")
        print(f"{i}) {name}")
        print(f"   ID: {identifier}")
        print(f"   Description: {description}")
        print()


def get_issuer_key():
    """Get issuer private key"""
    while True:
        issuer_nsec = input("Enter your private key (nsec): ").strip()
        if issuer_nsec.startswith("nsec1"):
            return issuer_nsec
        else:
            print("❌ Invalid format. Must start with 'nsec1'")


def get_recipients():
    """Get recipient pubkeys"""
    print("\n👥 Enter recipient pubkeys (one per line, empty line to finish):")
    recipients = []
    
    while True:
        recipient = input("Recipient: ").strip()
        if not recipient:
            break
        recipients.append(recipient)
    
    return recipients


async def create_badge_definition(badge_creator, badge_data, relay_urls):
    """Create and publish badge definition"""
    print(f"\n🏗️ Creating badge definition...")
    result = await badge_creator.publish_badge_definition(badge_data, relay_urls)
    
    if result['status'] == 'success':
        print(f"✅ Badge definition created successfully!")
        print(f"   A-tag: {result['a_tag']}")
        print(f"   Verified on {result['verified_relays']} relay(s)")
        return result['a_tag']
    else:
        print(f"⚠️ Badge definition published but not yet verified")
        print(f"   A-tag: {result['a_tag']}")
        return result['a_tag']


async def award_badge(badge_creator, a_tag, recipients, relay_urls):
    """Award badge to recipients"""
    print(f"\n🎯 Awarding badge to {len(recipients)} recipient(s)...")
    result = await badge_creator.award_badge(a_tag, recipients, relay_urls)
    
    if result['status'] == 'success':
        print(f"✅ Badge awarded successfully!")
        print(f"   Award Event ID: {result['event']['id']}")
        print(f"   Verified on {result['verified_relays']} relay(s)")
        return result['event']['id']
    else:
        print(f"⚠️ Badge awarded but not yet verified")
        print(f"   Award Event ID: {result['event']['id']}")
        return result['event']['id']


async def accept_badge():
    """Accept badge workflow"""
    print("\n🏅 Badge Acceptance Tool")
    print("=" * 50)
    
    # Get recipient key
    recipient_nsec = input("Enter your private key (nsec): ").strip()
    if not recipient_nsec.startswith("nsec1"):
        print("❌ Invalid format. Must start with 'nsec1'")
        return
    
    # Get badge info
    badge_definition_a_tag = input("Badge Definition A-tag: ").strip()
    badge_award_event_id = input("Badge Award Event ID: ").strip()
    
    # Load config
    config = load_config()
    relay_urls = config.get("relay_urls", [])
    
    # Accept badge
    acceptance_manager = BadgeAcceptanceManager(recipient_nsec)
    result = await acceptance_manager.accept_badge(
        badge_definition_a_tag, badge_award_event_id, relay_urls
    )
    
    if result["status"] == "success":
        print(f"🎉 BADGE ACCEPTED SUCCESSFULLY!")
        print(f"Profile Badges Event ID: {result['event']['id']}")
    else:
        print(f"⚠️ Badge accepted but not yet verified")


async def main():
    """Main badge tool workflow"""
    print("🏅 Nostr Badge Tool")
    print("=" * 50)
    
    # Load configuration
    config = load_config()
    relay_urls = config.get("relay_urls", [])
    print(f"📡 Using {len(relay_urls)} relays")
    
    # Get issuer key
    issuer_nsec = get_issuer_key()
    badge_creator = BadgeCreator(issuer_nsec)
    issuer_info = badge_creator.get_issuer_info()
    print(f"👤 Issuer: {issuer_info['npub']}")
    
    # Load badge definitions
    badges = load_badge_definitions()
    if not badges:
        print("❌ No badge definitions found in badges/definitions/")
        return
    
    # Display badges
    display_badges(badges)
    
    # Select badge
    try:
        choice = int(input("Select badge to award (number): ")) - 1
        badge_identifiers = list(badges.keys())
        if choice < 0 or choice >= len(badge_identifiers):
            print("❌ Invalid badge selection")
            return
        
        selected_identifier = badge_identifiers[choice]
        selected_badge = badges[selected_identifier]
        badge_name = next((tag[1] for tag in selected_badge['tags'] if tag[0] == 'name'), selected_identifier)
        print(f"✅ Selected: {badge_name}")
        
    except (ValueError, IndexError):
        print("❌ Invalid selection")
        return
    
    # Get recipients
    recipients = get_recipients()
    if not recipients:
        print("❌ No recipients provided")
        return
    
    print(f"\n🎯 Ready to award '{badge_name}' to {len(recipients)} recipient(s)")
    confirm = input("Proceed? (y/n): ").lower()
    if confirm != "y":
        print("❌ Cancelled")
        return
    
    # Create badge definition if needed
    print(f"\n🏗️ Creating badge definition...")
    badge_data = {
        "identifier": selected_identifier,
        "name": badge_name,
        "description": next((tag[1] for tag in selected_badge['tags'] if tag[0] == 'description'), ""),
        "image": next((tag[1] for tag in selected_badge['tags'] if tag[0] == 'image'), "")
    }
    
    a_tag = await create_badge_definition(badge_creator, badge_data, relay_urls)
    
    # Award badge
    award_event_id = await award_badge(badge_creator, a_tag, recipients, relay_urls)
    
    # Show results
    print(f"\n🎉 SUCCESS!")
    print(f"   Badge: {badge_name}")
    print(f"   A-tag: {a_tag}")
    print(f"   Award Event ID: {award_event_id}")
    print(f"   Recipients: {len(recipients)}")
    
    # Show acceptance instructions
    print(f"\n📋 For recipients to accept this badge:")
    print(f"   Badge Definition A-tag: {a_tag}")
    print(f"   Award Event ID: {award_event_id}")
    print(f"   Use: python3 badge_tool.py --accept")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Nostr Badge Tool")
    parser.add_argument("--accept", action="store_true", help="Accept badge mode")
    args = parser.parse_args()
    
    if args.accept:
        asyncio.run(accept_badge())
    else:
        asyncio.run(main())
