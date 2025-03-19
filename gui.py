import os
import tempfile
import time
# noinspection PyUnresolvedReferences
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, QLineEdit, QFileDialog, QFrame, QSlider, QListWidget, QListWidgetItem
from PyQt6.QtCore import Qt, QTimer
from protocol import Protocol
from threading import Thread

# Add the current script directory to PATH for portable DLL loading
os.environ["PATH"] = os.path.dirname(__file__) + os.pathsep + os.environ["PATH"]
import mpv


# noinspection PyUnresolvedReferences
class ClientGUI(QWidget):
    def __init__(self, client_socket):
        super().__init__()
        self.client_socket = client_socket
        self.player = mpv.MPV(
            wid='0',
            log_handler=self.mpv_log,
            vo='gpu',
            hwdec='auto'
        )
        self.layout = None
        self.video_frame = None
        self.movie_list = None
        self.controls_layout = None
        self.controls_widget = None
        self.open_file_button = None
        self.pause_button = None
        self.stop_button = None
        self.fullscreen_button = None
        self.volume_slider = None
        self.progress_slider = None
        self.input_field = None
        self.send_button = None
        self.response_box = None
        self.seeking = None
        self.listen_thread = None
        self.player.loop = False
        self.temp_file = None
        self.init_ui()
        self.start_listening()
        self.progress_timer = QTimer(self)
        self.progress_timer.timeout.connect(self.update_progress)
        self.progress_timer.start(1000)
        self.show()

    def init_ui(self):
        self.setWindowTitle("LOVETRIP")
        self.setGeometry(100, 100, 800, 600)

        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.video_frame = QFrame(self)
        self.video_frame.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Sunken)
        self.video_frame.setMinimumSize(640, 360)
        self.layout.addWidget(self.video_frame)
        self.player.wid = str(int(self.video_frame.winId()))

        self.movie_list = QListWidget(self)
        self.movie_list.itemDoubleClicked.connect(self.select_movie)
        self.layout.addWidget(self.movie_list)

        self.controls_widget = QWidget(self)
        self.controls_widget.setStyleSheet("background-color: rgba(0, 0, 0, 150);")
        self.controls_layout = QHBoxLayout(self.controls_widget)
        self.controls_layout.setContentsMargins(10, 0, 10, 10)

        self.open_file_button = QPushButton("Open Local File", self)
        self.pause_button = QPushButton("Pause", self)
        self.stop_button = QPushButton("Stop", self)
        self.fullscreen_button = QPushButton("Fullscreen", self)

        self.volume_slider = QSlider(Qt.Orientation.Horizontal, self)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)
        self.volume_slider.setFixedWidth(100)
        self.volume_slider.valueChanged.connect(self.set_volume)

        self.progress_slider = QSlider(Qt.Orientation.Horizontal, self)
        self.progress_slider.setRange(0, 100)
        self.progress_slider.setValue(0)
        self.progress_slider.setEnabled(False)
        self.progress_slider.setFixedWidth(300)
        self.progress_slider.sliderMoved.connect(self.seek_to_position)
        self.progress_slider.sliderPressed.connect(self.start_seeking)

        self.controls_layout.addWidget(self.open_file_button)
        self.controls_layout.addWidget(self.pause_button)
        self.controls_layout.addWidget(self.stop_button)
        self.controls_layout.addWidget(self.volume_slider)
        self.controls_layout.addWidget(self.progress_slider)
        self.controls_layout.addWidget(self.fullscreen_button)
        self.controls_layout.addStretch()

        bottom_layout = QVBoxLayout()
        self.input_field = QLineEdit(self)
        self.send_button = QPushButton("Send", self)
        self.response_box = QTextEdit(self)
        self.response_box.setReadOnly(True)
        self.response_box.setMaximumHeight(100)
        bottom_layout.addWidget(self.input_field)
        bottom_layout.addWidget(self.send_button)
        bottom_layout.addWidget(self.response_box)

        self.layout.addLayout(bottom_layout)

        self.setLayout(self.layout)

        self.send_button.clicked.connect(self.send_message)
        self.input_field.returnPressed.connect(self.send_message)
        self.open_file_button.clicked.connect(self.open_file)
        self.pause_button.clicked.connect(self.pause_media)
        self.stop_button.clicked.connect(self.stop_media)
        self.fullscreen_button.clicked.connect(self.toggle_fullscreen)

        self.adjust_controls_position()

    def send_message(self):
        message = self.input_field.text().strip()
        if message:
            try:
                Protocol.send(self.client_socket, message)
                self.input_field.clear()
            except Exception as e:
                self.response_box.append(f"Error sending message: {e}")

    def listen_for_responses(self):
        while True:
            try:
                message = Protocol.receive(self.client_socket)
                if not message:
                    self.response_box.append("Disconnected from server.")
                    break
                if message.startswith("MOVIES:"):
                    movies = message.split(":", 1)[1].split(";")
                    self.movie_list.clear()
                    for movie in movies:
                        if movie:
                            self.movie_list.addItem(movie)
                elif message.startswith("STREAMING:"):
                    movie_name = message.split(":", 1)[1]
                    self.response_box.append(f"Streaming {movie_name}")
                    self.temp_file = tempfile.NamedTemporaryFile(suffix='.mkv', delete=False)
                    bytes_received = 0
                    buffer_threshold = 50 * 1024 * 1024  # 50MB initial buffer
                    stream_buffer = b""
                    with open(self.temp_file.name, 'wb') as f:
                        while True:
                            data = self.client_socket.recv(1048576)  # 1MB chunks
                            if not data:
                                self.response_box.append("Stream interrupted: no data received.")
                                break
                            stream_buffer += data
                            if b"STREAM_END#" in stream_buffer:
                                video_data, _ = stream_buffer.split(b"STREAM_END#", 1)
                                if video_data:
                                    f.write(video_data)
                                self.response_box.append("Stream ended.")
                                self.play_streamed_file()  # Ensure playback continues
                                break
                            else:
                                f.write(data)
                                stream_buffer = b""
                                bytes_received += len(data)
                                self.response_box.append(f"Received {bytes_received // 1024 // 1024}MB")
                                if bytes_received >= buffer_threshold and not self.player.filename:
                                    self.play_streamed_file()
                    self.temp_file.close()
                elif message.startswith("ERROR:"):
                    self.response_box.append(f"Server error: {message}")
                else:
                    self.response_box.append(f"Server: {message}")
            except Exception as e:
                self.response_box.append(f"Error receiving response: {e}")
                break

    def play_streamed_file(self):
        if self.temp_file and os.path.exists(self.temp_file.name):
            try:
                self.player.stop()  # Clear any existing playback
                self.player.command('loadfile', self.temp_file.name, 'append-play')
                self.response_box.append("Started playback from temp file.")
                self.progress_slider.setEnabled(True)
            except Exception as e:
                self.response_box.append(f"Playback error: {e}")

    def select_movie(self, item):
        movie_name = item.text()
        Protocol.send(self.client_socket, f"SELECT:{movie_name}")
        self.response_box.append(f"Selected movie: {movie_name}")

    def start_listening(self):
        self.listen_thread = Thread(target=self.listen_for_responses, daemon=True)
        self.listen_thread.start()

    def open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Media File", "",
                                                   "Media Files (*.mp4 *.avi *.mkv *.mp3 *.wav)")
        if file_path:
            self.response_box.append(f"Selected file: {file_path}")
            self.player.playlist_clear()
            self.player.playlist_append(file_path)
            self.player.playlist_pos = 0
            self.progress_slider.setValue(0)
            self.progress_slider.setEnabled(True)

    def pause_media(self):
        if self.player.pause:
            self.player.pause = False
            self.response_box.append("Resumed media.")
        else:
            self.player.pause = True
            self.response_box.append("Paused media.")

    def stop_media(self):
        try:
            if self.player.filename:  # Only stop if something is playing
                self.player.stop()
            self.response_box.append("Stopped media.")
        except Exception as e:
            self.response_box.append(f"Stop error: {e}")
        self.progress_slider.setValue(0)
        self.progress_slider.setEnabled(False)
        if self.temp_file and os.path.exists(self.temp_file.name):
            self.temp_file = None  # Cleanup in closeEvent

    def set_volume(self, value):
        self.player.volume = value
        self.response_box.append(f"Volume set to {value}%")

    def update_progress(self):
        if self.player.duration and self.player.time_pos:
            progress = (self.player.time_pos / self.player.duration) * 100
            self.progress_slider.blockSignals(True)
            self.progress_slider.setValue(int(progress))
            self.progress_slider.blockSignals(False)

    def start_seeking(self):
        self.seeking = True

    def seek_to_position(self, value):
        if self.player.duration:
            seek_time = (value / 100) * self.player.duration
            self.player.time_pos = seek_time
            self.response_box.append(f"Seeking to {value}%")

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
            self.fullscreen_button.setText("Fullscreen")
        else:
            self.showFullScreen()
            self.fullscreen_button.setText("Exit Fullscreen")
        self.adjust_controls_position()

    def adjust_controls_position(self):
        video_rect = self.video_frame.geometry()
        controls_height = self.controls_widget.height()
        self.controls_widget.setGeometry(
            video_rect.left(),
            video_rect.bottom() - controls_height,
            video_rect.width(),
            controls_height
        )

    def mpv_log(self, loglevel, component, message):
        self.response_box.append(f"[MPV {loglevel}] {component}: {message}")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Space:
            self.pause_media()
            event.accept()
        else:
            super().keyPressEvent(event)

    def wheelEvent(self, event):
        widget = self.childAt(event.position().toPoint())
        if widget == self.volume_slider:
            delta = event.angleDelta().y() // 120
            new_value = min(max(self.volume_slider.value() + delta * 5, 0), 100)
            self.volume_slider.setValue(new_value)
        elif widget == self.progress_slider and self.progress_slider.isEnabled():
            delta = event.angleDelta().y() // 120
            new_value = min(max(self.progress_slider.value() + delta * 5, 0), 100)
            self.progress_slider.setValue(new_value)

    def mouseReleaseEvent(self, event):
        if self.progress_slider.isEnabled() and self.progress_slider.underMouse():
            pos = self.progress_slider.mapFromGlobal(event.globalPosition().toPoint())
            value = self.progress_slider.minimum() + (self.progress_slider.maximum() - self.progress_slider.minimum()) * pos.x() / self.progress_slider.width()
            value = min(max(int(value), 0), 100)
            self.seek_to_position(value)
        super().mouseReleaseEvent(event)

    def resizeEvent(self, event):
        self.adjust_controls_position()
        super().resizeEvent(event)

    def closeEvent(self, event):
        self.progress_timer.stop()
        self.player.terminate()
        if self.temp_file and os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)
        self.client_socket.close()
        event.accept()
