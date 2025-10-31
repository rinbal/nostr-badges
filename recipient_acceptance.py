"""
Recipient Badge Acceptance System
Implements NIP-58 Profile Badges (kind 30008) for badge display
"""

import json
import asyncio
import time
import websockets
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from nostr.key import PrivateKey
from nostr.event import Event
from relay_manager import RelayManager


class BadgeAcceptanceManager:
    """Manages badge acceptance and Profile Badges (kind 30008) creation"""
    
    def __init__(self, recipient_nsec: str):
        """Initialize with recipient's private key"""
        self.recipient_pk = PrivateKey.from_nsec(recipient_nsec)
        self.recipient_hex = self.recipient_pk.public_key.hex()
        self.recipient_npub = self.recipient_pk.public_key.bech32()
        
        # Initialize backup system
        self.backup_dir = Path("badge_backups")
        self.backup_dir.mkdir(exist_ok=True)
        self.max_backups = 5
    
    def create_profile_badges_event(
        self, 
        badge_awards: List[Dict[str, Any]], 
        relay_urls: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Create a Profile Badges event (kind 30008) to display awarded badges
        
        Args:
            badge_awards: List of badge award events to display
            relay_urls: Optional relay URLs for 'e' tags
        
        Returns:
            Signed Profile Badges event
        """
        # Create tags for Profile Badges event
        tags = [["d", "profile_badges"]]
        
        # Add badge definition and award pairs
        for award in badge_awards:
            # Extract badge definition reference from award's 'a' tag
            a_tag = next((tag for tag in award.get("tags", []) if tag[0] == "a"), None)
            if a_tag:
                tags.append(["a", a_tag[1]])  # Badge definition reference
            
            # Add award event reference with optional relay URL
            e_tag = ["e", award["id"]]
            if relay_urls:
                e_tag.extend(relay_urls[:1])  # Add first relay URL
            tags.append(e_tag)
        
        # Create the event
        event = {
            "kind": 30008,
            "created_at": int(time.time()),
            "content": f"Profile badges: {len(badge_awards)} badges displayed",
            "tags": tags
        }
        
        # Sign the event
        ev = Event(
            kind=event["kind"],
            content=event["content"],
            tags=event["tags"]
        )
        self.recipient_pk.sign_event(ev)
        
        # Return signed event
        return {
            "id": ev.id,
            "pubkey": self.recipient_hex,
            "created_at": int(ev.created_at),
            "kind": ev.kind,
            "tags": ev.tags,
            "content": ev.content,
            "sig": getattr(ev, "signature", None) or getattr(ev, "sig", None)
        }
    
    def create_simple_profile_badges(
        self,
        badge_definition_a_tag: str,
        badge_award_event_id: str,
        relay_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a simple Profile Badges event for a single badge
        
        Args:
            badge_definition_a_tag: The 'a' tag from the badge award
            badge_award_event_id: The event ID of the badge award
            relay_url: Optional relay URL for the 'e' tag
        
        Returns:
            Signed Profile Badges event
        """
        # Create tags
        tags = [
            ["d", "profile_badges"],
            ["a", badge_definition_a_tag]
        ]
        
        # Add award event reference
        e_tag = ["e", badge_award_event_id]
        if relay_url:
            e_tag.append(relay_url)
        tags.append(e_tag)
        
        # Create and sign event
        event = {
            "kind": 30008,
            "created_at": int(time.time()),
            "content": "Profile badges: 1 badge displayed",
            "tags": tags
        }
        
        ev = Event(
            kind=event["kind"],
            content=event["content"],
            tags=event["tags"]
        )
        self.recipient_pk.sign_event(ev)
        
        return {
            "id": ev.id,
            "pubkey": self.recipient_hex,
            "created_at": int(ev.created_at),
            "kind": ev.kind,
            "tags": ev.tags,
            "content": ev.content,
            "sig": getattr(ev, "signature", None) or getattr(ev, "sig", None)
        }
    
    async def accept_badge(
        self,
        badge_definition_a_tag: str,
        badge_award_event_id: str,
        relay_urls: List[str]
    ) -> Dict[str, Any]:
        """
        Bulletproof badge acceptance with comprehensive error handling
        
        Returns:
            Result dictionary with status and event information
        """
        print(f"🏅 Accepting badge...")
        print(f"   Badge Definition: {badge_definition_a_tag}")
        print(f"   Award Event ID: {badge_award_event_id}")
        
        try:
            # 1. Fetch existing Profile Badges event
            print("🔍 Fetching existing badges...")
            existing_event = await self.fetch_existing_profile_badges(relay_urls)
            
            # 2. Parse existing badge pairs
            existing_pairs = []
            if existing_event:
                existing_pairs = self.parse_profile_badges_pairs(existing_event.get("tags", []))
                print(f"   Found {len(existing_pairs)} existing badges")
            
            # 3. Create new badge pair
            new_pair = (badge_definition_a_tag, badge_award_event_id)
            
            # 4. Bulletproof merge with comprehensive error handling
            print("🔄 Merging badges with safety checks...")
            merge_success, merge_error, merged_pairs = self.merge_badge_pairs(existing_pairs, new_pair)
            
            if not merge_success:
                print(f"❌ Merge failed: {merge_error}")
                return {
                    "status": "merge_failed",
                    "error": merge_error,
                    "existing_badges": len(existing_pairs),
                    "recovered_badges": len(merged_pairs)
                }
            
            print(f"   Merged to {len(merged_pairs)} total badges")
            
            # 5. Create merged Profile Badges event
            profile_badges_event = self.create_merged_profile_badges_event(
                merged_pairs, relay_urls
            )
            
            # 6. Create backup before publishing
            print("💾 Creating backup before publishing...")
            self.create_backup(merged_pairs, profile_badges_event["id"])
            
            # 7. Publish to relays
            print("📡 Publishing to relays...")
            relay_manager = RelayManager()
            results = await relay_manager.publish_event(profile_badges_event, relay_urls)
            relay_manager.print_summary()
            
            # 8. Check results
            verified_count = sum(1 for r in results if r.verified)
            
            if verified_count > 0:
                print(f"✅ Badge accepted and displayed on {verified_count} relay(s)")
                print(f"   Total badges now displayed: {len(merged_pairs)}")
                
                # 9. Clean up old backups after successful publish
                self.cleanup_old_backups()
                
                return {
                    "status": "success",
                    "event": profile_badges_event,
                    "verified_relays": verified_count,
                    "total_badges": len(merged_pairs)
                }
            else:
                print("⚠️ Badge accepted but not yet verified")
                return {
                    "status": "published_unverified",
                    "event": profile_badges_event,
                    "verified_relays": 0,
                    "total_badges": len(merged_pairs)
                }
                
        except Exception as e:
            print(f"❌ Badge acceptance failed: {e}")
            print("🔄 Attempting to recover from backup...")
            
            # Try to recover from backup
            backup_pairs = self.load_latest_backup()
            if backup_pairs:
                print(f"✅ Recovered {len(backup_pairs)} badges from backup")
                return {
                    "status": "recovered_from_backup",
                    "error": str(e),
                    "recovered_badges": len(backup_pairs)
                }
            else:
                return {
                    "status": "failed",
                    "error": str(e),
                    "recovered_badges": 0
                }
    
    async def generate_manual_instructions(
        self,
        badge_definition_a_tag: str,
        badge_award_event_id: str,
        relay_urls: List[str],
        relay_url: Optional[str] = None
    ) -> str:
        """
        Generate manual instructions for accepting a badge with merge functionality
        
        Returns:
            Formatted instructions string
        """
        # Fetch existing badges for merge instructions
        print("🔍 Fetching existing badges for merge instructions...")
        existing_event = await self.fetch_existing_profile_badges(relay_urls)
        
        existing_pairs = []
        if existing_event:
            existing_pairs = self.parse_profile_badges_pairs(existing_event.get("tags", []))
        
        # Create new badge pair
        new_pair = (badge_definition_a_tag, badge_award_event_id)
        
        # Bulletproof merge with error handling
        merge_success, merge_error, merged_pairs = self.merge_badge_pairs(existing_pairs, new_pair)
        
        if not merge_success:
            print(f"⚠️ Merge failed for manual instructions: {merge_error}")
            # Use existing pairs if merge fails
            merged_pairs = existing_pairs
        
        # Create the merged Profile Badges event structure
        tags = [["d", "profile_badges"]]
        for a_val, e_val in merged_pairs:
            tags.append(["a", a_val])
            e_tag = ["e", e_val]
            if relay_url:
                e_tag.append(relay_url)
            tags.append(e_tag)
        
        profile_badges_event = {
            "kind": 30008,
            "content": f"Profile badges: {len(merged_pairs)} badges displayed",
            "tags": tags
        }
        
        instructions = f"""
🏅 BADGE ACCEPTANCE INSTRUCTIONS (WITH MERGE)
============================================

To display this badge in your profile, you need to create/update a Profile Badges event (kind 30008).

📋 BADGE INFORMATION:
- Badge Definition: {badge_definition_a_tag}
- Award Event ID: {badge_award_event_id}
- Your Public Key: {self.recipient_npub}
- Existing Badges: {len(existing_pairs)}
- Total Badges After Merge: {len(merged_pairs)}

🔧 MANUAL ACCEPTANCE (WITH MERGE):

1. Open your nostr client that supports NIP-58 badges
2. Create a new event with kind 30008
3. Use these exact tags (includes all your badges):
{chr(10).join([f"   - {tag[0]}: {tag[1]}" for tag in tags])}

4. Sign and publish the event to relays

📝 PREFILLED JSON (copy and paste):
```json
{json.dumps(profile_badges_event, indent=2)}
```

⚠️ IMPORTANT: This will replace your existing Profile Badges event with a merged version that includes all your badges.

💡 The badge will then be visible in your profile in nostr clients that support NIP-58!
        """
        return instructions.strip()
    
    def get_recipient_info(self) -> Dict[str, str]:
        """Get recipient information"""
        return {
            "hex": self.recipient_hex,
            "npub": self.recipient_npub
        }
    
    def validate_badge_pair(self, a_tag: str, e_tag: str) -> Tuple[bool, str]:
        """
        Validate a badge pair for correctness
        
        Args:
            a_tag: Badge definition A-tag
            e_tag: Badge award event ID
            
        Returns:
            (is_valid, error_message)
        """
        # Validate A-tag format
        if not a_tag.startswith("30009:"):
            return False, f"Invalid A-tag format: {a_tag}"
        
        # Validate A-tag structure (should be 30009:pubkey:identifier)
        parts = a_tag.split(":")
        if len(parts) != 3:
            return False, f"Invalid A-tag structure: {a_tag}"
        
        pubkey_part, identifier_part = parts[1], parts[2]
        
        # Validate pubkey (should be 64-char hex)
        if len(pubkey_part) != 64 or not all(c in "0123456789abcdef" for c in pubkey_part.lower()):
            return False, f"Invalid pubkey in A-tag: {pubkey_part}"
        
        # Validate identifier (should not be empty)
        if not identifier_part:
            return False, f"Empty identifier in A-tag: {a_tag}"
        
        # Validate E-tag (should be 64-char hex)
        if len(e_tag) != 64 or not all(c in "0123456789abcdef" for c in e_tag.lower()):
            return False, f"Invalid event ID: {e_tag}"
        
        return True, ""
    
    def validate_badge_pairs(self, pairs: List[Tuple[str, str]]) -> Tuple[bool, str, List[Tuple[str, str]]]:
        """
        Validate a list of badge pairs and return valid ones
        
        Args:
            pairs: List of (a_tag, e_tag) pairs
            
        Returns:
            (all_valid, error_message, valid_pairs)
        """
        valid_pairs = []
        errors = []
        
        for i, (a_tag, e_tag) in enumerate(pairs):
            is_valid, error = self.validate_badge_pair(a_tag, e_tag)
            if is_valid:
                valid_pairs.append((a_tag, e_tag))
            else:
                errors.append(f"Pair {i+1}: {error}")
        
        if errors:
            return False, "; ".join(errors), valid_pairs
        
        return True, "", valid_pairs
    
    def create_backup(self, badge_pairs: List[Tuple[str, str]], event_id: str) -> bool:
        """
        Create a backup of badge pairs before merge
        
        Args:
            badge_pairs: List of badge pairs to backup
            event_id: Event ID for the backup
            
        Returns:
            True if backup successful, False otherwise
        """
        try:
            timestamp = int(time.time())
            backup_data = {
                "timestamp": timestamp,
                "event_id": event_id,
                "recipient_hex": self.recipient_hex,
                "badge_pairs": badge_pairs,
                "total_badges": len(badge_pairs)
            }
            
            backup_file = self.backup_dir / f"profile_badges_{timestamp}_{event_id[:8]}.json"
            
            with open(backup_file, "w", encoding="utf-8") as f:
                json.dump(backup_data, f, indent=2)
            
            print(f"💾 Backup created: {backup_file}")
            return True
            
        except Exception as e:
            print(f"⚠️ Backup creation failed: {e}")
            return False
    
    def cleanup_old_backups(self) -> None:
        """Clean up old backups, keeping only the last max_backups"""
        try:
            backup_files = list(self.backup_dir.glob("profile_badges_*.json"))
            backup_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            # Keep only the most recent backups
            files_to_delete = backup_files[self.max_backups:]
            
            for file_path in files_to_delete:
                file_path.unlink()
                print(f"🗑️ Deleted old backup: {file_path.name}")
                
        except Exception as e:
            print(f"⚠️ Backup cleanup failed: {e}")
    
    def load_latest_backup(self) -> Optional[List[Tuple[str, str]]]:
        """
        Load the latest backup of badge pairs
        
        Returns:
            List of badge pairs or None if no backup found
        """
        try:
            backup_files = list(self.backup_dir.glob("profile_badges_*.json"))
            if not backup_files:
                return None
            
            # Get the most recent backup
            latest_backup = max(backup_files, key=lambda x: x.stat().st_mtime)
            
            with open(latest_backup, "r", encoding="utf-8") as f:
                backup_data = json.load(f)
            
            badge_pairs = [(pair[0], pair[1]) for pair in backup_data["badge_pairs"]]
            print(f"📂 Loaded backup: {latest_backup.name} ({len(badge_pairs)} badges)")
            return badge_pairs
            
        except Exception as e:
            print(f"⚠️ Backup loading failed: {e}")
            return None
    
    def parse_profile_badges_pairs(self, tags: List[List[str]]) -> List[Tuple[str, str]]:
        """
        Parse existing Profile Badges pairs from tags
        
        Args:
            tags: List of tags from existing Profile Badges event
            
        Returns:
            List of (a_tag, e_tag) pairs
        """
        pairs = []
        i = 0
        while i < len(tags):
            if tags[i][0] == "a":
                a_val = tags[i][1]
                e_val = None
                # Check if next tag is 'e'
                if i + 1 < len(tags) and tags[i + 1][0] == "e":
                    e_val = tags[i + 1][1]
                    i += 1  # Skip the 'e' tag
                pairs.append((a_val, e_val))
            i += 1
        return pairs
    
    async def fetch_existing_profile_badges(self, relay_urls: List[str]) -> Optional[Dict[str, Any]]:
        """
        Fetch existing Profile Badges event (kind 30008) for this recipient
        
        Args:
            relay_urls: List of relay URLs to query
            
        Returns:
            Latest Profile Badges event or None if not found
        """
        filter_payload = {
            "kinds": [30008],
            "authors": [self.recipient_hex],
            "#d": ["profile_badges"],
            "limit": 1
        }
        
        for relay in relay_urls:
            try:
                async with websockets.connect(relay, open_timeout=5) as ws:
                    req_id = f"fetch_profile_badges_{int(time.time())}"
                    await ws.send(json.dumps(["REQ", req_id, filter_payload]))
                    
                    start_time = time.time()
                    while time.time() - start_time < 4:
                        try:
                            response = await asyncio.wait_for(ws.recv(), timeout=2)
                            data = json.loads(response)
                            
                            if isinstance(data, list) and data[0] == "EVENT" and len(data) >= 3:
                                if data[1] == req_id:
                                    event = data[2]
                                    if isinstance(event, dict) and event.get("kind") == 30008:
                                        print(f"✅ Found existing Profile Badges on {relay}")
                                        return event
                            
                            elif isinstance(data, list) and data[0] == "EOSE" and len(data) >= 2:
                                if data[1] == req_id:
                                    break
                                    
                        except asyncio.TimeoutError:
                            break
                        except Exception:
                            continue
                            
            except Exception as e:
                print(f"⚠️ Failed to query {relay}: {e}")
                continue
        
        print("ℹ️ No existing Profile Badges found")
        return None
    
    def merge_badge_pairs(
        self, 
        existing_pairs: List[Tuple[str, str]], 
        new_pair: Tuple[str, str]
    ) -> Tuple[bool, str, List[Tuple[str, str]]]:
        """
        Bulletproof merge of existing badge pairs with new pair
        
        Args:
            existing_pairs: List of existing (a_tag, e_tag) pairs
            new_pair: New (a_tag, e_tag) pair to add
            
        Returns:
            (success, error_message, merged_pairs)
        """
        try:
            # Step 1: Validate existing pairs
            if existing_pairs:
                is_valid, error, valid_existing = self.validate_badge_pairs(existing_pairs)
                if not is_valid:
                    print(f"⚠️ Invalid existing pairs found: {error}")
                    print("🔄 Attempting to recover from backup...")
                    
                    # Try to recover from backup
                    backup_pairs = self.load_latest_backup()
                    if backup_pairs:
                        existing_pairs = backup_pairs
                        print(f"✅ Recovered {len(backup_pairs)} badges from backup")
                    else:
                        print("⚠️ No backup available, using empty list")
                        existing_pairs = []
                else:
                    existing_pairs = valid_existing
            
            # Step 2: Validate new pair
            is_valid, error = self.validate_badge_pair(new_pair[0], new_pair[1])
            if not is_valid:
                return False, f"Invalid new badge pair: {error}", existing_pairs
            
            # Step 3: Create backup of existing pairs before merge
            if existing_pairs:
                backup_id = f"pre_merge_{int(time.time())}"
                self.create_backup(existing_pairs, backup_id)
            
            # Step 4: Combine existing and new pairs
            all_pairs = existing_pairs + [new_pair]
            
            # Step 5: Deduplicate while preserving order
            seen = set()
            deduped = []
            for a_val, e_val in all_pairs:
                key = (a_val, e_val)
                if key not in seen:
                    seen.add(key)
                    deduped.append((a_val, e_val))
            
            # Step 6: Validate merged result
            is_valid, error, valid_merged = self.validate_badge_pairs(deduped)
            if not is_valid:
                print(f"❌ Merge validation failed: {error}")
                print("🔄 Rolling back to existing pairs...")
                return False, f"Merge validation failed: {error}", existing_pairs
            
            # Step 7: Final safety check - ensure we didn't lose badges
            if len(deduped) < len(existing_pairs):
                print(f"❌ Merge resulted in badge loss: {len(existing_pairs)} -> {len(deduped)}")
                print("🔄 Rolling back to existing pairs...")
                return False, "Merge resulted in badge loss", existing_pairs
            
            print(f"✅ Merge successful: {len(existing_pairs)} -> {len(deduped)} badges")
            return True, "", deduped
            
        except Exception as e:
            print(f"❌ Merge failed with exception: {e}")
            print("🔄 Attempting to recover from backup...")
            
            # Try to recover from backup
            backup_pairs = self.load_latest_backup()
            if backup_pairs:
                return False, f"Merge failed, recovered from backup: {e}", backup_pairs
            else:
                return False, f"Merge failed, no backup available: {e}", existing_pairs
    
    def create_merged_profile_badges_event(
        self, 
        badge_pairs: List[Tuple[str, str]], 
        relay_urls: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Create a merged Profile Badges event with all badge pairs
        
        Args:
            badge_pairs: List of (a_tag, e_tag) pairs
            relay_urls: Optional relay URLs for 'e' tags
            
        Returns:
            Signed Profile Badges event
        """
        # Start with required 'd' tag
        tags = [["d", "profile_badges"]]
        
        # Add all badge pairs as a/e interleaved tags
        for a_val, e_val in badge_pairs:
            tags.append(["a", a_val])
            e_tag = ["e", e_val]
            if relay_urls:
                e_tag.append(relay_urls[0])  # Add first relay URL
            tags.append(e_tag)
        
        # Create and sign event
        event = {
            "kind": 30008,
            "created_at": int(time.time()),
            "content": f"Profile badges: {len(badge_pairs)} badges displayed",
            "tags": tags
        }
        
        ev = Event(
            kind=event["kind"],
            content=event["content"],
            tags=event["tags"]
        )
        self.recipient_pk.sign_event(ev)
        
        return {
            "id": ev.id,
            "pubkey": self.recipient_hex,
            "created_at": int(ev.created_at),
            "kind": ev.kind,
            "tags": ev.tags,
            "content": ev.content,
            "sig": getattr(ev, "signature", None) or getattr(ev, "sig", None)
        }
