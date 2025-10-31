import json
import asyncio
import time
import websockets
from nostr.key import PrivateKey
from nostr.event import Event
from datetime import datetime


# ==============================================================
#   SIGN EVENT (Kind 8 or 30009)
# ==============================================================

def sign_event(event_dict, nsec):
    """Sign an unsigned Nostr event using issuer's nsec. Ensures full NIP-01 compliance."""
    pk = PrivateKey.from_nsec(nsec)

    # create event
    ev = Event(
        kind=event_dict["kind"],
        content=event_dict["content"],
        tags=event_dict["tags"]
    )

    # sign
    pk.sign_event(ev)

    signature = getattr(ev, "signature", None) or getattr(ev, "sig", None)

    # Fully NIP-01 compliant JSON object
    signed_event = {
        "id": ev.id,
        "pubkey": pk.public_key.hex(),         # 💡 Force HEX (not bech32)
        "created_at": int(ev.created_at),      # 💡 float to int for relay compatibility
        "kind": ev.kind,
        "tags": ev.tags,
        "content": ev.content,
        "sig": signature,
    }

    # Optional: save to file
    folder = "tool/data/events"
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    path = f"{folder}/signed_event_{timestamp}.json"

    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(signed_event, f, indent=2)
        print(f"💾 Signed event saved: {path}")
    except Exception as e:
        print(f"⚠️ Could not save signed event: {e}")

    print(f"🆔 Event ID: {ev.id}")
    return signed_event


# ==============================================================
#   CHECK RELAY NIP-58 SUPPORT
# ==============================================================

async def test_nip58_support(relay):
    """Check if relay supports NIP-58 by testing event publishing."""
    try:
        async with websockets.connect(relay, open_timeout=3) as ws:
            # Test with a minimal NIP-58 compliant badge definition
            test_event = {
                "kind": 30009,
                "created_at": int(time.time()),
                "content": "Test badge definition",
                "tags": [
                    ["d", "test-badge-nip58"],
                    ["name", "Test Badge"]
                ],
                "pubkey": "0000000000000000000000000000000000000000000000000000000000000000",
                "id": "test",
                "sig": "test"
            }
            
            await ws.send(json.dumps(["EVENT", test_event]))
            try:
                response = await asyncio.wait_for(ws.recv(), timeout=3)
                # Check if relay accepts the event (even if it's invalid due to fake signature)
                if '"OK"' in response or '"true"' in response:
                    return True
            except asyncio.TimeoutError:
                return False
    except Exception:
        return False
    return False


# ==============================================================
#   PUBLISH EVENT
# ==============================================================

async def publish_event(event, relays):
    """Publish a signed event to multiple relays with detailed diagnostics.

    Diagnostics include NIP-20 OK/NOTICE/CLOSED parsing and post-publish
    verification by querying the event back by id.
    """

    def _parse_message(raw):
        try:
            data = json.loads(raw)
            if isinstance(data, list) and data:
                return data
        except Exception:
            pass
        return None

    results = []

    for relay in relays:
        relay_result = {
            "relay": relay,
            "sent": False,
            "ok": None,
            "ok_msg": None,
            "notice": [],
            "closed": None,
            "retrievable": False,
            "error": None,
        }

        # Optional: keep the quick gate, but do not skip diagnostics entirely
        try:
            nip58_ok = await test_nip58_support(relay)
        except Exception:
            nip58_ok = False

        if not nip58_ok:
            print(f"⚠️ {relay} may not support NIP-58. Attempting publish anyway...")

        try:
            async with websockets.connect(relay, open_timeout=5) as ws:
                await ws.send(json.dumps(["EVENT", event]))
                relay_result["sent"] = True
                print(f"📡 Sent to {relay}, awaiting responses (OK/NOTICE/CLOSED)...")

                # Read multiple frames for a short window to capture OK/NOTICE/CLOSED
                ok_received = False
                start = time.time()
                while time.time() - start < 5:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=1.5)
                    except asyncio.TimeoutError:
                        break

                    parsed = _parse_message(raw)
                    if not parsed:
                        continue

                    mtype = parsed[0]
                    if mtype == "OK" and len(parsed) >= 4:
                        _, ev_id, accepted, message = parsed[:4]
                        if ev_id == event.get("id"):
                            relay_result["ok"] = bool(accepted)
                            relay_result["ok_msg"] = message
                            ok_received = True
                            print(f"   OK from {relay}: accepted={accepted} msg={message}")
                            if not accepted:
                                # If relay explicitly rejected, no need to continue
                                break
                    elif mtype == "NOTICE" and len(parsed) >= 2:
                        relay_result["notice"].append(parsed[1])
                        print(f"   NOTICE from {relay}: {parsed[1]}")
                    elif mtype == "CLOSED" and len(parsed) >= 3:
                        relay_result["closed"] = parsed[2]
                        print(f"   CLOSED from {relay}: {parsed[2]}")

                # Post-publish verification: REQ the event id back
                try:
                    req_id = f"verify:{event['id'][:8]}"
                    flt = {"ids": [event["id"]], "limit": 1}
                    await ws.send(json.dumps(["REQ", req_id, flt]))
                    saw_event = False
                    start_req = time.time()
                    while time.time() - start_req < 4:
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=1.5)
                        except asyncio.TimeoutError:
                            break
                        parsed = _parse_message(raw)
                        if not parsed:
                            continue
                        if parsed[0] == "EVENT" and len(parsed) >= 3 and parsed[1] == req_id:
                            ev = parsed[2]
                            if isinstance(ev, dict) and ev.get("id") == event.get("id"):
                                saw_event = True
                        if parsed[0] == "EOSE" and len(parsed) >= 2 and parsed[1] == req_id:
                            break
                    relay_result["retrievable"] = saw_event
                    if saw_event:
                        print(f"   🔎 Verified retrievable on {relay}.")
                    else:
                        print(f"   ⚠️ Not retrievable (yet) on {relay}.")
                except Exception as e:
                    print(f"   ⚠️ Verification query failed on {relay}: {e}")

        except Exception as e:
            relay_result["error"] = str(e)
            print(f"❌ Failed to publish to {relay}: {e}")

        results.append(relay_result)

    # Summary
    print("\n────────────────────────────")
    print("📊 Publish Summary (per relay):")
    ok_count = sum(1 for r in results if r["ok"]) 
    ret_count = sum(1 for r in results if r["retrievable"]) 
    print(f"  OK true:   {ok_count}/{len(results)}")
    print(f"  Retrieved: {ret_count}/{len(results)}")
    for r in results:
        status = "OK✅" if r["ok"] else ("OK❌" if r["ok"] is not None else "No OK")
        retr = "retrievable" if r["retrievable"] else "not retrievable"
        err = f" error={r['error']}" if r["error"] else ""
        print(f"  {r['relay']}: {status}, {retr}.{err}")
        if r["ok_msg"]:
            print(f"    ok_msg: {r['ok_msg']}")
        for n in r["notice"]:
            print(f"    notice: {n}")
        if r["closed"]:
            print(f"    closed: {r['closed']}")
    print("────────────────────────────")
