import os
import time
import json
import asyncio
import websockets
from pathlib import Path
from datetime import datetime
from utils.file_utils import load_json, save_json
from nostr_utils import sign_event
from relay_manager import RelayManager


# ==============================================================
#   LOAD & DISPLAY BADGES
# ==============================================================

def load_all_badges():
    """Load all badge definitions (sorted alphabetically)."""
    folder = Path(__file__).parent / "badges" / "definitions"
    badges = {}
    for file in folder.glob("*.json"):
        data = load_json(file)
        badges[file.stem] = data
    return dict(sorted(badges.items()))


def display_badges(badges):
    """Display all badges in order."""
    print("\nAvailable badges:")
    print("────────────────────────────")
    for i, (key, badge) in enumerate(sorted(badges.items()), start=1):
        try:
            name = next(tag[1] for tag in badge["tags"] if tag[0] == "name")
            desc = next(tag[1] for tag in badge["tags"] if tag[0] == "description")
            print(f"[{i}] {name} — {desc}")
        except StopIteration:
            print(f"[{i}] {key} — ⚠️ Missing name or description tag")


# ==============================================================
#   CREATE AWARD EVENT (Kind 8)
# ==============================================================

def create_award_event(badge, issuer_nsec, recipient_pubkey_hex):
    """Create a Kind 8 award event following NIP-58."""
    from nostr.key import PrivateKey
    import time
    pk = PrivateKey.from_nsec(issuer_nsec)

    identifier = next(tag[1] for tag in badge["tags"] if tag[0] == "d")
    name = next(tag[1] for tag in badge["tags"] if tag[0] == "name")

    # NIP-58 compliant Badge Award event - ONLY a and p tags allowed
    event = {
        "kind": 8,
        "created_at": int(time.time()),  # Use time.time() for current timestamp
        "content": f"Awarded badge: {name}",
        "tags": [
            ["a", f"30009:{pk.public_key.hex()}:{identifier}"],
            ["p", recipient_pubkey_hex]
        ],
    }

    return event


def save_award_event(event, badge_name):
    """Save award event locally (unsigned)."""
    folder = Path(__file__).parent / "data" / "events"
    folder.mkdir(parents=True, exist_ok=True)
    filename = f"award_{badge_name}_{int(time.time())}.json"
    path = folder / filename
    save_json(path, event)
    print(f"\n✅ Award event saved successfully: {path}")


# ==============================================================
#   PUBLISH BADGE DEFINITION (Kind 30009)
# ==============================================================

PUBLISHED_DB = Path(__file__).parent / "data" / "published_definitions.json"


def _load_published_db():
    try:
        return load_json(PUBLISHED_DB)
    except Exception:
        return {}


def _save_published_db(db):
    save_json(PUBLISHED_DB, db)


async def _query_relays_for_definition(relay_urls, issuer_hex, d_value, timeout=4):
    """Ask relays if badge definition (Kind 30009) already exists.

    Reads until EOSE per relay and returns the first matching EVENT payload.
    """
    filter_payload = {"kinds": [30009], "authors": [issuer_hex], "#d": [d_value], "limit": 1}

    async def _query_single(relay):
        req_id = f"req_def:{d_value[:8]}:{int(time.time())}"
        try:
            async with websockets.connect(relay) as ws:
                await ws.send(json.dumps(["REQ", req_id, filter_payload]))
                start = time.time()
                while time.time() - start < timeout:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=1.5)
                    except asyncio.TimeoutError:
                        break
                    try:
                        msg = json.loads(raw)
                    except Exception:
                        continue
                    if not (isinstance(msg, list) and msg):
                        continue
                    if msg[0] == "EVENT" and len(msg) >= 3 and msg[1] == req_id:
                        return msg[2]
                    if msg[0] == "EOSE" and len(msg) >= 2 and msg[1] == req_id:
                        break
        except Exception:
            return None
        return None

    for relay in relay_urls:
        ev = await _query_single(relay)
        if ev:
            return ev
    return None


def query_definition_on_relays(relay_urls, issuer_hex, d_value, timeout=3):
    """Sync wrapper."""
    try:
        return asyncio.run(_query_relays_for_definition(relay_urls, issuer_hex, d_value, timeout))
    except Exception:
        return None


def publish_definition_if_missing(badge, issuer_nsec, issuer_hex, issuer_npub, relay_urls):
    """Ensure badge definition exists, else publish it."""
    identifier = next(tag[1] for tag in badge["tags"] if tag[0] == "d")
    name = next((tag[1] for tag in badge["tags"] if tag[0] == "name"), "")
    desc = next((tag[1] for tag in badge["tags"] if tag[0] == "description"), "")
    image = next((tag[1] for tag in badge["tags"] if tag[0] == "image"), None)

    db = _load_published_db()
    key = f"{issuer_hex}:{identifier}"

    # Step 1: check local cache
    if key in db:
        print(f"ℹ️ Definition for '{name}' already marked as published locally.")
        return {"status": "exists", "event": db[key]}

    # Step 2: check relays
    existing = query_definition_on_relays(relay_urls, issuer_hex, identifier)
    if existing:
        print(f"✅ Definition for '{name}' already exists on relays.")
        db[key] = existing
        _save_published_db(db)
        return {"status": "exists", "event": existing}

    # Step 3: create & publish
    print(f"\n🛠️  Publishing new badge definition for '{name}' ...")

    # NIP-58 compliant Badge Definition event - ONLY standard tags allowed
    definition_event = {
        "kind": 30009,
        "created_at": int(time.time()),
        "content": f"Badge definition: {name}",
        "tags": [
            ["d", identifier],
            ["name", name],
            ["description", desc]
        ],
    }
    if image:
        definition_event["tags"].append(["image", image])

    try:
        signed = sign_event(definition_event, issuer_nsec)
        
        # Use advanced relay manager for better diagnostics
        relay_manager = RelayManager()
        results = asyncio.run(relay_manager.publish_event(signed, relay_urls))
        relay_manager.print_summary()
        
        # Check if at least one relay verified the event
        verified_count = sum(1 for r in results if r.verified)
        if verified_count > 0:
            db[key] = signed
            _save_published_db(db)
            print(f"✅ Badge definition '{name}' published and verified on {verified_count} relay(s)!")
            return {"status": "published", "event": signed}
        else:
            print(f"⚠️ Badge definition published but not yet verified. It may take a few minutes.")
            return {"status": "published_unverified", "event": signed}
    except Exception as e:
        print(f"❌ Failed to publish badge definition: {e}")
        return {"status": "error", "error": str(e)}
