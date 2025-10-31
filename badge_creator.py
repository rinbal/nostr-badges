"""
Nostr Badge Creator Tool - NIP-58 Compliant
Focused on badge creation and awarding only
"""

import json
import asyncio
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from nostr.key import PrivateKey
from nostr.event import Event
from relay_manager import RelayManager


class BadgeCreator:
    """Nostr Badge Creator - Handles Badge Definitions and Awards only"""
    
    def __init__(self, issuer_nsec: str):
        """Initialize badge creator with issuer private key"""
        self.issuer_pk = PrivateKey.from_nsec(issuer_nsec)
        self.issuer_hex = self.issuer_pk.public_key.hex()
        self.issuer_npub = self.issuer_pk.public_key.bech32()
        
    def create_badge_definition(self, badge_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a Badge Definition event (kind 30009) following NIP-58
        
        Args:
            badge_data: Dictionary with badge information
                - identifier: Unique badge identifier (required)
                - name: Badge name (optional)
                - description: Badge description (optional)
                - image: Image URL (optional)
                - thumb: Thumbnail URLs (optional)
        
        Returns:
            Signed Badge Definition event
        """
        # Extract required identifier
        identifier = badge_data["identifier"]
        
        # Create NIP-58 compliant tags
        tags = [["d", identifier]]
        
        # Add optional tags
        if "name" in badge_data:
            tags.append(["name", badge_data["name"]])
        if "description" in badge_data:
            tags.append(["description", badge_data["description"]])
        if "image" in badge_data:
            tags.append(["image", badge_data["image"]])
        if "thumb" in badge_data:
            for thumb in badge_data["thumb"]:
                tags.append(["thumb", thumb])
        
        # Create event
        event = {
            "kind": 30009,
            "created_at": int(time.time()),
            "content": f"Badge definition: {badge_data.get('name', identifier)}",
            "tags": tags
        }
        
        # Sign event
        ev = Event(
            kind=event["kind"],
            content=event["content"],
            tags=event["tags"]
        )
        self.issuer_pk.sign_event(ev)
        
        # Return signed event
        return {
            "id": ev.id,
            "pubkey": self.issuer_hex,
            "created_at": int(ev.created_at),
            "kind": ev.kind,
            "tags": ev.tags,
            "content": ev.content,
            "sig": getattr(ev, "signature", None) or getattr(ev, "sig", None)
        }
    
    def create_badge_award(self, badge_definition_a_tag: str, recipient_pubkeys: List[str]) -> Dict[str, Any]:
        """
        Create a Badge Award event (kind 8) following NIP-58
        
        Args:
            badge_definition_a_tag: The 'a' tag from Badge Definition (e.g., "30009:pubkey:identifier")
            recipient_pubkeys: List of recipient pubkeys (hex format)
        
        Returns:
            Signed Badge Award event
        """
        # Create NIP-58 compliant tags
        tags = [["a", badge_definition_a_tag]]
        
        # Add recipient pubkeys
        for pubkey in recipient_pubkeys:
            tags.append(["p", pubkey])
        
        # Create event
        event = {
            "kind": 8,
            "created_at": int(time.time()),
            "content": f"Awarded badge to {len(recipient_pubkeys)} recipient(s)",
            "tags": tags
        }
        
        # Sign event
        ev = Event(
            kind=event["kind"],
            content=event["content"],
            tags=event["tags"]
        )
        self.issuer_pk.sign_event(ev)
        
        # Return signed event
        return {
            "id": ev.id,
            "pubkey": self.issuer_hex,
            "created_at": int(ev.created_at),
            "kind": ev.kind,
            "tags": ev.tags,
            "content": ev.content,
            "sig": getattr(ev, "signature", None) or getattr(ev, "sig", None)
        }
    
    async def publish_badge_definition(self, badge_data: Dict[str, Any], relay_urls: List[str]) -> Dict[str, Any]:
        """
        Create and publish a Badge Definition event
        
        Returns:
            Result dictionary with status and event information
        """
        print(f"🏗️ Creating badge definition: {badge_data.get('name', badge_data['identifier'])}")
        
        # Create badge definition
        definition_event = self.create_badge_definition(badge_data)
        
        # Publish to relays
        relay_manager = RelayManager()
        results = await relay_manager.publish_event(definition_event, relay_urls)
        relay_manager.print_summary()
        
        # Check results
        verified_count = sum(1 for r in results if r.verified)
        
        if verified_count > 0:
            print(f"✅ Badge definition published and verified on {verified_count} relay(s)")
            return {
                "status": "success",
                "event": definition_event,
                "verified_relays": verified_count,
                "a_tag": f"30009:{self.issuer_hex}:{badge_data['identifier']}"
            }
        else:
            print("⚠️ Badge definition published but not yet verified")
            return {
                "status": "published_unverified",
                "event": definition_event,
                "verified_relays": 0,
                "a_tag": f"30009:{self.issuer_hex}:{badge_data['identifier']}"
            }
    
    async def award_badge(self, badge_definition_a_tag: str, recipient_pubkeys: List[str], relay_urls: List[str]) -> Dict[str, Any]:
        """
        Create and publish a Badge Award event
        
        Args:
            badge_definition_a_tag: The 'a' tag from Badge Definition
            recipient_pubkeys: List of recipient pubkeys (hex format)
            relay_urls: List of relay URLs to publish to
        
        Returns:
            Result dictionary with status and event information
        """
        print(f"🏅 Awarding badge to {len(recipient_pubkeys)} recipient(s)")
        
        # Create badge award
        award_event = self.create_badge_award(badge_definition_a_tag, recipient_pubkeys)
        
        # Publish to relays
        relay_manager = RelayManager()
        results = await relay_manager.publish_event(award_event, relay_urls)
        relay_manager.print_summary()
        
        # Check results
        verified_count = sum(1 for r in results if r.verified)
        
        if verified_count > 0:
            print(f"✅ Badge award published and verified on {verified_count} relay(s)")
            return {
                "status": "success",
                "event": award_event,
                "verified_relays": verified_count,
                "recipients": recipient_pubkeys
            }
        else:
            print("⚠️ Badge award published but not yet verified")
            return {
                "status": "published_unverified",
                "event": award_event,
                "verified_relays": 0,
                "recipients": recipient_pubkeys
            }
    
    def get_issuer_info(self) -> Dict[str, str]:
        """Get issuer information"""
        return {
            "hex": self.issuer_hex,
            "npub": self.issuer_npub
        }


def normalize_pubkey(pubkey: str) -> str:
    """Normalize pubkey to hex format"""
    if pubkey.startswith("npub1"):
        from nostr.key import PublicKey
        pub = PublicKey.from_npub(pubkey)
        return pub.hex()
    elif all(c in "0123456789abcdef" for c in pubkey.lower()) and len(pubkey) == 64:
        return pubkey
    else:
        raise ValueError("Invalid pubkey format. Must be npub1... or 64-char hex")


def normalize_pubkey_to_npub(pubkey: str) -> str:
    """Convert pubkey to npub format"""
    if pubkey.startswith("npub1"):
        return pubkey
    elif all(c in "0123456789abcdef" for c in pubkey.lower()) and len(pubkey) == 64:
        from nostr.key import PublicKey
        pub = PublicKey(bytes.fromhex(pubkey))
        return pub.bech32()
    else:
        raise ValueError("Invalid pubkey format. Must be npub1... or 64-char hex")
