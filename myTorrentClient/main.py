# File: main.py
# -----------------------------
import asyncio
import aiohttp
import os
import sys
from torrent_parser.parser import TorrentParser
from tracker.client import TrackerClient
from peer.connection import PeerConnection
from pieces.manager import PieceManager
from pieces.storage import Storage

async def main(torrent_path_or_url):
    # Step 1: If URL, download torrent file
    if torrent_path_or_url.startswith(('http://', 'https://')):
        print("[Main] Detected torrent URL, downloading...")
        async with aiohttp.ClientSession() as session:
            async with session.get(torrent_path_or_url) as resp:
                data = await resp.read()
                filename = os.path.basename(torrent_path_or_url)
                with open(filename, 'wb') as f:
                    f.write(data)
                torrent_path_or_url = filename
                print(f"[Main] Torrent file saved as {filename}")

    # Step 2: Parse metadata
    parser = TorrentParser(torrent_path_or_url)
    metadata = parser.parse()

    # Step 3: Initialize storage and piece manager
    storage = Storage(metadata['name'], metadata['length'], metadata['piece_length'])
    piece_manager = PieceManager(metadata)

    # Step 4: Get peers
    tracker = TrackerClient(metadata)
    peers = await tracker.get_peers()
    if not peers:
        print("[Main] No peers found, exiting.")
        return

    # Step 5: Connect to peers in parallel
    tasks = []
    for peer in peers:
        conn = PeerConnection(peer, metadata, piece_manager, storage)
        tasks.append(asyncio.create_task(conn.start()))

    await asyncio.gather(*tasks)
    print("[Main] Download tasks complete.")

if __name__ == '__main__':
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(main(sys.argv[1]))
    except Exception as e:
        print("[Main] Error:", e)
    finally:
        if not loop.is_closed():
            loop.close()
