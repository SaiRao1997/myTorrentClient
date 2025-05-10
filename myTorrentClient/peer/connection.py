# File: peer/connection.py
# -----------------------------
import asyncio
import struct
import random
import hashlib

class PeerConnection:
    def __init__(self, peer, metadata, piece_manager, storage):
        self.peer = peer
        self.metadata = metadata
        self.piece_manager = piece_manager
        self.storage = storage
        self.available = set()

    async def start(self):
        ip, port = self.peer
        print(f"[PeerConnection] Connecting to {ip}:{port}")
        try:
            reader, writer = await asyncio.open_connection(ip, port)
            # Handshake
            writer.write(self.build_handshake())
            await writer.drain()
            resp = await reader.readexactly(68)
            if resp[1:20] != b'BitTorrent protocol':
                print("[PeerConnection] Invalid handshake")
                return
            print("[PeerConnection] Handshake OK")
            # Interested
            writer.write(struct.pack('>IB', 1, 2)); await writer.drain()
            print("[PeerConnection] Sent interested")

            # Read messages until unchoke, parsing bitfield
            while True:
                header = await reader.readexactly(4)
                length = struct.unpack('>I', header)[0]
                if length == 0:
                    continue  # keep-alive
                msg_id = (await reader.readexactly(1))[0]
                body_len = length - 1
                if msg_id == 5:  # bitfield
                    bitfield = await reader.readexactly(body_len)
                    self._parse_bitfield(bitfield)
                    print(f"[PeerConnection] Bitfield parsed: {len(self.available)} pieces available")
                elif msg_id == 1:  # unchoke
                    await reader.readexactly(body_len)
                    print("[PeerConnection] Unchoked")
                    break
                else:
                    await reader.readexactly(body_len)

            # Download loop: request only pieces this peer has
            total_pieces = len(self.piece_manager.hash_list)
            while True:
                # Find next available piece
                idx = None
                while True:
                    candidate = self.piece_manager.next_piece()
                    if candidate is None:
                        break
                    if candidate in self.available:
                        idx = candidate
                        break
                if idx is None:
                    print("[PeerConnection] No more available pieces to request from this peer")
                    break

                begin = 0
                length = self.metadata['piece_length']
                # Request piece
                writer.write(struct.pack('>IBIII', 13, 6, idx, begin, length))
                await writer.drain()
                print(f"[PeerConnection] Requested piece {idx}")

                # Read piece message
                header = await reader.readexactly(4)
                size = struct.unpack('>I', header)[0]
                msg_id = (await reader.readexactly(1))[0]
                if msg_id != 7:
                    print(f"[PeerConnection] Expected piece (id 7), got {msg_id}")
                    await reader.readexactly(size - 1)
                    continue
                await reader.readexactly(8)  # skip index & begin
                block = await reader.readexactly(size - 9)
                print(f"[PeerConnection] Received block size {len(block)} for piece {idx}")

                # Verify and store
                expected = self.piece_manager.expected_hash(idx)
                if hashlib.sha1(block).digest() == expected:
                    self.storage.write_block(idx, begin, block)
                    print(f"[PeerConnection] Stored piece {idx}")
                else:
                    print(f"[PeerConnection] Hash mismatch for piece {idx}")

            writer.close()
            await writer.wait_closed()
        except Exception as e:
            print(f"[PeerConnection] Error: {e}")

    def build_handshake(self):
        pstr = b'BitTorrent protocol'
        peer_id = b'-PC0001-' + bytes([random.randint(0, 255) for _ in range(12)])
        return bytes([len(pstr)]) + pstr + bytes(8) + self.metadata['info_hash'] + peer_id

    def _parse_bitfield(self, bitfield):
        total = len(self.piece_manager.hash_list)
        for byte_index, byte in enumerate(bitfield):
            for bit in range(8):
                if byte & (1 << (7 - bit)):
                    piece = byte_index * 8 + bit
                    if piece < total:
                        self.available.add(piece)

    async def wait_for_unchoke(self, reader):
        # Unused: bitfield logic moved into start(), so this can be removed or kept minimal
        pass

# -----------------------------