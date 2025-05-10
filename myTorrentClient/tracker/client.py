# File: tracker/client.py
# -----------------------------
import aiohttp
import socket
import struct
import random
import urllib.parse
import bencodepy

class TrackerClient:
    def __init__(self, metadata):
        self.metadata = metadata

    async def get_peers(self):
        print("[TrackerClient] Getting peers from tracker...")
        url = self._build_announce_url()
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.read()
                if data.startswith(b'<'):
                    print("[TrackerClient] Invalid tracker response (HTML)")
                    return []
                try:
                    decoded = bencodepy.decode(data)
                except Exception as err:
                    print("[TrackerClient] Decode error:", err)
                    return []
                if b'failure reason' in decoded:
                    print("[TrackerClient] Tracker failure:", decoded[b'failure reason'].decode(errors='ignore'))
                    return []
                peers = []
                pd = decoded.get(b'peers') or decoded.get(b'peers6')
                if not pd:
                    print("[TrackerClient] No peers in response")
                    return []
                for i in range(0, len(pd), 6):
                    ip = socket.inet_ntoa(pd[i:i+4])
                    port = struct.unpack('>H', pd[i+4:i+6])[0]
                    peers.append((ip, port))
                return peers

    def _build_announce_url(self):
        orig = self.metadata['announce']
        tracker_url = orig
        if orig.startswith('udp://'):
            print(f"[TrackerClient] UDP announce, switching to HTTP fallback")
            tracker_url = 'http://tracker.opentrackr.org:1337/announce'
        ih = urllib.parse.quote_from_bytes(self.metadata['info_hash'])
        pid = (b'-PC0001-' + bytes(random.randint(0,9) for _ in range(12)))
        params = {
            'info_hash': ih,
            'peer_id': pid,
            'port': 6881,
            'uploaded': 0,
            'downloaded': 0,
            'left': self.metadata['length'],
            'compact': 1,
            'event': 'started'
        }
        parts = []
        for k,v in params.items():
            if isinstance(v, bytes):
                parts.append(f"{k}={urllib.parse.quote_from_bytes(v)}")
            else:
                parts.append(f"{k}={v}")
        return f"{tracker_url}?{'&'.join(parts)}"

