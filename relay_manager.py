"""
Advanced Relay Management for Nostr Badge Tool
Handles connection, publishing, and verification with proper error handling
"""

import json
import asyncio
import time
import websockets
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class RelayResult:
    """Result of a relay operation"""
    relay: str
    connected: bool = False
    published: bool = False
    verified: bool = False
    error: Optional[str] = None
    ok_message: Optional[str] = None
    notice_messages: List[str] = None
    
    def __post_init__(self):
        if self.notice_messages is None:
            self.notice_messages = []


class RelayManager:
    """Advanced relay management with proper error handling and verification"""
    
    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.results: List[RelayResult] = []
    
    async def publish_event(self, event: Dict[str, Any], relays: List[str]) -> List[RelayResult]:
        """Publish event to multiple relays with comprehensive diagnostics"""
        self.results = []
        
        for relay in relays:
            result = RelayResult(relay=relay)
            self.results.append(result)
            
            try:
                await self._publish_to_single_relay(event, result)
            except Exception as e:
                result.error = str(e)
                print(f"❌ Failed to publish to {relay}: {e}")
        
        return self.results
    
    async def _publish_to_single_relay(self, event: Dict[str, Any], result: RelayResult):
        """Publish to a single relay with full diagnostics"""
        try:
            async with websockets.connect(result.relay, open_timeout=self.timeout) as ws:
                result.connected = True
                print(f"📡 Connected to {result.relay}")
                
                # Send event
                await ws.send(json.dumps(["EVENT", event]))
                print(f"📤 Sent event to {result.relay}")
                
                # Wait for responses
                await self._handle_relay_responses(ws, result, event)
                
                # Verify event was stored
                await self._verify_event_storage(ws, result, event)
                
        except websockets.exceptions.ConnectionClosed as e:
            result.error = f"Connection closed: {e}"
        except asyncio.TimeoutError:
            result.error = "Connection timeout"
        except Exception as e:
            result.error = f"Unexpected error: {e}"
    
    async def _handle_relay_responses(self, ws, result: RelayResult, event: Dict[str, Any]):
        """Handle OK/NOTICE/CLOSED responses from relay"""
        start_time = time.time()
        
        while time.time() - start_time < 5:  # 5 second timeout
            try:
                response = await asyncio.wait_for(ws.recv(), timeout=2)
                parsed = self._parse_message(response)
                
                if not parsed:
                    continue
                
                msg_type = parsed[0]
                
                if msg_type == "OK" and len(parsed) >= 4:
                    event_id, accepted, message = parsed[1], parsed[2], parsed[3]
                    if event_id == event.get("id"):
                        result.published = bool(accepted)
                        result.ok_message = message
                        print(f"   ✅ {result.relay}: OK accepted={accepted} msg='{message}'")
                        if not accepted:
                            result.error = f"Relay rejected: {message}"
                            return
                
                elif msg_type == "NOTICE" and len(parsed) >= 2:
                    notice_msg = parsed[1]
                    result.notice_messages.append(notice_msg)
                    print(f"   ℹ️ {result.relay}: NOTICE '{notice_msg}'")
                
                elif msg_type == "CLOSED" and len(parsed) >= 3:
                    reason = parsed[2]
                    result.error = f"Connection closed: {reason}"
                    print(f"   🔒 {result.relay}: CLOSED '{reason}'")
                    return
                    
            except asyncio.TimeoutError:
                break
            except Exception as e:
                print(f"   ⚠️ {result.relay}: Error reading response: {e}")
                break
    
    async def _verify_event_storage(self, ws, result: RelayResult, event: Dict[str, Any]):
        """Verify that the event was actually stored by the relay"""
        try:
            req_id = f"verify_{event['id'][:8]}"
            filter_payload = {"ids": [event["id"]], "limit": 1}
            
            await ws.send(json.dumps(["REQ", req_id, filter_payload]))
            print(f"   🔍 Verifying storage on {result.relay}...")
            
            start_time = time.time()
            while time.time() - start_time < 4:
                try:
                    response = await asyncio.wait_for(ws.recv(), timeout=1)
                    parsed = self._parse_message(response)
                    
                    if not parsed:
                        continue
                    
                    if parsed[0] == "EVENT" and len(parsed) >= 3 and parsed[1] == req_id:
                        stored_event = parsed[2]
                        if isinstance(stored_event, dict) and stored_event.get("id") == event.get("id"):
                            result.verified = True
                            print(f"   ✅ Verified: Event stored on {result.relay}")
                            return
                    
                    elif parsed[0] == "EOSE" and len(parsed) >= 2 and parsed[1] == req_id:
                        break
                        
                except asyncio.TimeoutError:
                    break
            
            if not result.verified:
                print(f"   ⚠️ Could not verify storage on {result.relay}")
                
        except Exception as e:
            print(f"   ⚠️ Verification failed on {result.relay}: {e}")
    
    def _parse_message(self, raw_message: str) -> Optional[List]:
        """Parse JSON message from relay"""
        try:
            data = json.loads(raw_message)
            if isinstance(data, list) and data:
                return data
        except (json.JSONDecodeError, TypeError):
            pass
        return None
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of relay operations"""
        total = len(self.results)
        connected = sum(1 for r in self.results if r.connected)
        published = sum(1 for r in self.results if r.published)
        verified = sum(1 for r in self.results if r.verified)
        
        return {
            "total": total,
            "connected": connected,
            "published": published,
            "verified": verified,
            "success_rate": f"{verified}/{total}" if total > 0 else "0/0"
        }
    
    def print_summary(self):
        """Print detailed summary of relay operations"""
        print("\n" + "="*60)
        print("📊 RELAY PUBLISH SUMMARY")
        print("="*60)
        
        summary = self.get_summary()
        print(f"Total Relays:    {summary['total']}")
        print(f"Connected:       {summary['connected']}")
        print(f"Published:       {summary['published']}")
        print(f"Verified:        {summary['verified']}")
        print(f"Success Rate:    {summary['success_rate']}")
        
        print("\nPer-Relay Details:")
        for result in self.results:
            status = "✅" if result.verified else ("⚠️" if result.published else "❌")
            print(f"  {status} {result.relay}")
            
            if result.error:
                print(f"    Error: {result.error}")
            if result.ok_message:
                print(f"    OK: {result.ok_message}")
            for notice in result.notice_messages:
                print(f"    Notice: {notice}")
        
        print("="*60)
