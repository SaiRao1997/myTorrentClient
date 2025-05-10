# File: pieces/manager.py
# -----------------------------
import hashlib

class PieceManager:
    def __init__(self, metadata):
        self.metadata = metadata
        hashes = metadata['pieces']
        self.hash_list = [hashes[i:i+20] for i in range(0, len(hashes), 20)]
        self.next_idx = 0

    def next_piece(self):
        if self.next_idx < len(self.hash_list):
            idx = self.next_idx
            self.next_idx += 1
            return idx
        return None

    def expected_hash(self, index):
        return self.hash_list[index]

