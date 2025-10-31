#!/usr/bin/env python3
"""
Profile Badges Helper - Create Profile Badges events for NIP-58
Usage: python3 profile_badges_helper.py <nsec> <badge_definition_a_tag> <badge_award_event_id> [relay_url]
"""

import sys
import json
import asyncio
from pathlib import Path
from profile_badges import ProfileBadgesManager
from relay_manager import RelayManager


def main():
    if len(sys.argv) < 4:
        print("Usage: python3 profile_badges_helper.py <nsec> <badge_definition_a_tag> <badge_award_event_id> [relay_url]")
        print("\nExample:")
        print("python3 profile_badges_helper.py nsec1... 30009:pubkey:identifier event_id_here")
        sys.exit(1)
    
    recipient_nsec = sys.argv[1]
    badge_definition_a_tag = sys.argv[2]
    badge_award_event_id = sys.argv[3]
    relay_url = sys.argv[4] if len(sys.argv) > 4 else None
    
    print("🏅 Creating Profile Badges event...")
    print(f"Badge Definition: {badge_definition_a_tag}")
    print(f"Award Event ID: {badge_award_event_id}")
    
    try:
        # Create Profile Badges event
        profile_badges_event = ProfileBadgesManager.create_simple_profile_badges(
            recipient_nsec=recipient_nsec,
            badge_definition_a_tag=badge_definition_a_tag,
            badge_award_event_id=badge_award_event_id,
            relay_url=relay_url
        )
        
        print(f"\n✅ Profile Badges event created!")
        print(f"Event ID: {profile_badges_event['id']}")
        
        # Save event locally
        events_dir = Path("data/events")
        events_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"profile_badges_{int(time.time())}.json"
        filepath = events_dir / filename
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(profile_badges_event, f, indent=2)
        
        print(f"💾 Event saved: {filepath}")
        
        # Ask if user wants to publish
        publish = input("\nDo you want to publish this Profile Badges event? (y/n): ").lower()
        if publish == "y":
            # Load relay URLs from config
            try:
                with open("config.json", "r") as f:
                    config = json.load(f)
                relay_urls = config.get("relay_urls", [])
            except:
                relay_urls = [
                    "wss://relay.damus.io",
                    "wss://nos.lol",
                    "wss://nostr.wine"
                ]
            
            print(f"\n📡 Publishing to {len(relay_urls)} relays...")
            
            # Publish using RelayManager
            relay_manager = RelayManager()
            results = asyncio.run(relay_manager.publish_event(profile_badges_event, relay_urls))
            relay_manager.print_summary()
            
            # Check if successful
            verified_count = sum(1 for r in results if r.verified)
            if verified_count > 0:
                print(f"\n🎉 SUCCESS! Profile Badges event published and verified on {verified_count} relay(s)")
                print("Your badge should now be visible in nostr clients that support NIP-58!")
            else:
                print(f"\n⚠️ Event published but not yet verified. It may take a few minutes to appear.")
        
        else:
            print("ℹ️ Event saved but not published. You can publish it later.")
    
    except Exception as e:
        print(f"❌ Error creating Profile Badges event: {e}")
        sys.exit(1)


if __name__ == "__main__":
    import time
    main()
