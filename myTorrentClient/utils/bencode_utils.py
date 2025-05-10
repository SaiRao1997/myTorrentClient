# Folder: utils/bencode_utils.py
# -----------------------------
# Optional custom bencode
# -----------------------------
class PieceManager:
    def __init__(self, metadata):
        self.metadata = metadata
    def next_piece(self): pass
    def verify_piece(self, data, h): pass
