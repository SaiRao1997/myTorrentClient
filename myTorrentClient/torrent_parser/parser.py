# File: torrent_parser/parser.py
# -----------------------------
import bencodepy
import hashlib

class TorrentParser:
    def __init__(self, filepath):
        self.filepath = filepath

    def parse(self):
        raw = open(self.filepath, 'rb').read()
        data = bencodepy.decode(raw)
        info = data[b'info']
        info_encoded = bencodepy.encode(info)
        info_hash = hashlib.sha1(info_encoded).digest()
        length = info.get(b'length') or sum(f[b'length'] for f in info[b'files'])
        return {
            'announce': data[b'announce'].decode(),
            'info_hash': info_hash,
            'piece_length': info[b'piece length'],
            'pieces': info[b'pieces'],
            'length': length,
            'name': info[b'name'].decode()
        }