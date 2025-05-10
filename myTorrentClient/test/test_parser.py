# File: test/test_parser.py
# -----------------------------
import os
from torrent_parser.parser import TorrentParser

def test_parser():
    # Ensure sample.torrent exists in project root
    path = os.path.join(os.path.dirname(__file__), '..', 'sample.torrent')
    md = TorrentParser(path).parse()
    assert 'announce' in md and 'info_hash' in md and 'pieces' in md
