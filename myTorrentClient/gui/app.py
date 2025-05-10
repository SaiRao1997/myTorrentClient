# File: gui/app.py
# PyQt5 modern GUI for myTorrentClient with pause/play/stop and speed control

import sys
import os
import json
import asyncio
import threading
import time
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTableWidget, QTableWidgetItem, QProgressBar,
    QToolBar, QAction, QFileDialog, QLineEdit,
    QWidget, QVBoxLayout, QLabel, QDialog, QFormLayout, QSlider, QComboBox,
    QSplitter, QTextEdit, QPushButton, QHBoxLayout
)
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt, pyqtSignal, QObject

# Ensure project root for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from torrent_parser.parser import TorrentParser
from tracker.client import TrackerClient
from peer.connection import PeerConnection
from pieces.manager import PieceManager
from pieces.storage import Storage

CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'config.json')

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        layout = QFormLayout(self)
        self.config = {'upload_limit': 0, 'download_limit': 0, 'theme': 'Light'}
        if os.path.exists(CONFIG_PATH):
            try:
                self.config.update(json.load(open(CONFIG_PATH)))
            except:
                pass
        self.up_slider = QSlider(Qt.Horizontal)
        self.up_slider.setRange(0, 10000)
        self.up_slider.setValue(self.config['upload_limit'])
        layout.addRow("Upload Limit (KB/s):", self.up_slider)
        self.down_slider = QSlider(Qt.Horizontal)
        self.down_slider.setRange(0, 10000)
        self.down_slider.setValue(self.config['download_limit'])
        layout.addRow("Download Limit (KB/s):", self.down_slider)
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(['Light', 'Dark'])
        self.theme_combo.setCurrentText(self.config['theme'])
        layout.addRow("Theme:", self.theme_combo)
        save_btn = QAction("Save", self)
        save_btn.triggered.connect(self.save)
        layout.addRow(save_btn)

    def save(self):
        cfg = {'upload_limit': self.up_slider.value(),
               'download_limit': self.down_slider.value(),
               'theme': self.theme_combo.currentText()}
        with open(CONFIG_PATH, 'w') as f:
            json.dump(cfg, f)
        self.accept()

class Worker(QObject):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, int)

    def __init__(self, source, row, table):
        super().__init__()
        self.source = source
        self.row = row
        self.table = table
        cfg = {'download_limit': 0}
        if os.path.exists(CONFIG_PATH):
            try:
                cfg.update(json.load(open(CONFIG_PATH)))
            except:
                pass
        self.down_limit = cfg['download_limit'] * 1024  # bytes/sec
        self.paused = False
        self.stopped = False

    def pause(self):
        self.paused = True
        self.log_signal.emit(f"[Worker] Paused row {self.row}")

    def resume(self):
        self.paused = False
        self.log_signal.emit(f"[Worker] Resumed row {self.row}")

    def stop(self):
        self.stopped = True
        self.log_signal.emit(f"[Worker] Stopped row {self.row}")

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.download())

    async def download(self):
        parser = TorrentParser(self.source)
        metadata = parser.parse()
        storage = Storage(metadata['name'], metadata['length'], metadata['piece_length'])
        manager = PieceManager(metadata)
        peers = await TrackerClient(metadata).get_peers()
        if not peers:
            self.log_signal.emit("[Worker] No peers found.")
            return
        conn = PeerConnection(peers[0], metadata, manager, storage)
        total = len(manager.hash_list)
        for i in range(total):
            if self.stopped:
                break
            while self.paused:
                await asyncio.sleep(0.2)
            start = time.time()
            try:
                block_size = await conn.start_single(i, return_size=True)
                elapsed = time.time() - start
                if self.down_limit > 0 and elapsed > 0:
                    to_sleep = max(0, block_size / self.down_limit - elapsed)
                    await asyncio.sleep(to_sleep)
                percent = int((i+1)/total * 100)
                self.progress_signal.emit(self.row, percent)
                self.log_signal.emit(f"[Worker] Piece {i+1}/{total} completed")
            except Exception as e:
                self.log_signal.emit(f"[Worker] Error on piece {i}: {e}")
                break
        self.log_signal.emit("[Worker] Download finished.")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("myTorrentClient")
        self.resize(900, 600)
        self._load_theme()
        self._init_ui()

    def _load_theme(self):
        theme = 'Light'
        if os.path.exists(CONFIG_PATH):
            try:
                theme = json.load(open(CONFIG_PATH)).get('theme', 'Light')
            except:
                pass
        if theme == 'Dark':
            self.setStyleSheet(
                "QWidget{background:#2b2b2b;color:#f0f0f0;}"
                "QTableWidget{gridline-color:#444;}"
                "QHeaderView::section{background:#444;color:#f0f0f0;}"
                "QProgressBar{background:#444;border:1px solid #333;}"
                "QProgressBar::chunk{background:#05B8CC;}"
            )

    def _init_ui(self):
        toolbar = QToolBar()
        self.addToolBar(toolbar)
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText('Enter .torrent URL or leave blank to browse')
        self.url_edit.setFixedWidth(350)
        toolbar.addWidget(self.url_edit)
        add_action = QAction(QIcon.fromTheme('list-add'), 'Add', self)
        add_action.triggered.connect(self.add_torrent)
        toolbar.addAction(add_action)
        settings_action = QAction(QIcon.fromTheme('preferences-system'), 'Settings', self)
        settings_action.triggered.connect(self.open_settings)
        toolbar.addAction(settings_action)

        splitter = QSplitter(Qt.Vertical)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(['Name','Size','Progress','Speed','Actions',''])
        self.table.horizontalHeader().setStretchLastSection(True)
        splitter.addWidget(self.table)
        self.log = QTextEdit(readOnly=True)
        splitter.addWidget(self.log)
        splitter.setSizes([350,200])
        self.setCentralWidget(splitter)

    def add_torrent(self):
        src = self.url_edit.text().strip()
        if src:
            self.url_edit.clear()
            source = src
        else:
            source, _ = QFileDialog.getOpenFileName(self, 'Select .torrent', '', 'Torrent Files (*.torrent)')
            if not source:
                return
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row,0,QTableWidgetItem(os.path.basename(source)))
        self.table.setItem(row,1,QTableWidgetItem('0 MB'))
        pb = QProgressBar(); pb.setValue(0)
        self.table.setCellWidget(row,2,pb)
        self.table.setItem(row,3,QTableWidgetItem('0 KB/s'))
        # Actions: play, pause, stop
        action_widget = QWidget(); h = QHBoxLayout(action_widget); h.setContentsMargins(0,0,0,0)
        play_btn = QPushButton(QIcon.fromTheme('media-playback-start'), '')
        pause_btn = QPushButton(QIcon.fromTheme('media-playback-pause'), '')
        stop_btn = QPushButton(QIcon.fromTheme('media-playback-stop'), '')
        h.addWidget(play_btn); h.addWidget(pause_btn); h.addWidget(stop_btn)
        self.table.setCellWidget(row,4, action_widget)
        # Worker
        worker = Worker(source, row, self.table)
        play_btn.clicked.connect(worker.resume)
        pause_btn.clicked.connect(worker.pause)
        stop_btn.clicked.connect(worker.stop)
        worker.log_signal.connect(self._append_log)
        worker.progress_signal.connect(self._update_progress)
        thread = threading.Thread(target=worker.run, daemon=True)
        thread.start()

    def _update_progress(self,row,percent):
        widget = self.table.cellWidget(row,2)
        if isinstance(widget, QProgressBar): widget.setValue(percent)

    def _append_log(self,msg):
        self.log.append(msg)

    def open_settings(self):
        dlg = SettingsDialog(self)
        dlg.exec_()

if __name__=='__main__':
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())
