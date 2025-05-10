# File: pieces/storage.py
# -----------------------------
import os

class Storage:
    def __init__(self, filename, total_length, piece_length):
        self.filename = filename
        self.piece_length = piece_length
        # Pre-allocate file
        with open(filename, 'wb') as f:
            f.truncate(total_length)

    def write_block(self, index, offset, data):
        with open(self.filename, 'r+b') as f:
            f.seek(index * self.piece_length + offset)
            f.write(data)
