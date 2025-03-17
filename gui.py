import sys
import os
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, QLineEdit, QFileDialog, QFrame, QSlider
from PyQt6.QtCore import Qt, QTimer
from protocol import Protocol
from threading import Thread
# Add the current script directory to PATH for portable DLL loading
os.environ["PATH"] = os.path.dirname(__file__) + os.pathsep + os.environ["PATH"]
import mpv


# noinspection PyUnresolvedReferences,PyAttributeOutsideInit
class ClientGUI(QWidget):
    def __init__(self, client_socket):
        super().__init__()
        self.client_socket = client_socket
        self.player = mpv.MPV(
            wid='0',                     # Temporary, set to video frame later
            log_handler=self.mpv_log,    # Optional: Log MPV output to response box
            vo='gpu',                    # Use GPU for video output
            hwdec='auto'                 # Hardware decoding if available
        )
        self.player.loop = False
        self.init_ui()
        self.start_listening()
        # Timer to update progress bar
        self.progress_timer = QTimer(self)
        self.progress_timer.timeout.connect(self.update_progress)
        self.progress_timer.start(1000)  # Update every second
        self.show()

    def init_ui(self):
        """Initialize the GUI components."""
        self.setWindowTitle("Multimedia Client (MPV)")
        self.setGeometry(100, 100, 800, 600)

        # Main layout
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)  # No margins for fullscreen

        # Video frame
        self.video_frame = QFrame(self)
        self.video_frame.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Sunken)
        self.video_frame.setMinimumSize(640, 360)
        self.layout.addWidget(self.video_frame)

        # Set MPV to render in the video frame
        self.player.wid = str(int(self.video_frame.winId()))

        # Controls overlay (separate from video frame)
        self.controls_widget = QWidget(self)  # Parent is the main window, not video_frame
        self.controls_widget.setStyleSheet("background-color: rgba(0, 0, 0, 150);")  # Semi-transparent black
        self.controls_layout = QHBoxLayout(self.controls_widget)
        self.controls_layout.setContentsMargins(10, 0, 10, 10)  # Padding

        # Media control buttons
        self.open_file_button = QPushButton("Open Local File", self)
        self.pause_button = QPushButton("Pause", self)
        self.stop_button = QPushButton("Stop", self)
        self.fullscreen_button = QPushButton("Fullscreen", self)

        # Volume slider
        self.volume_slider = QSlider(Qt.Orientation.Horizontal, self)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)
        self.volume_slider.setFixedWidth(100)
        self.volume_slider.valueChanged.connect(self.set_volume)

        # Progress slider
        self.progress_slider = QSlider(Qt.Orientation.Horizontal, self)
        self.progress_slider.setRange(0, 100)
        self.progress_slider.setValue(0)
        self.progress_slider.setEnabled(False)  # Disabled until media loaded
        self.progress_slider.setFixedWidth(300)
        self.progress_slider.sliderMoved.connect(self.seek_to_position)
        self.progress_slider.sliderPressed.connect(self.start_seeking)

        # Add widgets to controls layout
        self.controls_layout.addWidget(self.open_file_button)
        self.controls_layout.addWidget(self.pause_button)
        self.controls_layout.addWidget(self.stop_button)
        self.controls_layout.addWidget(self.volume_slider)
        self.controls_layout.addWidget(self.progress_slider)
        self.controls_layout.addWidget(self.fullscreen_button)
        self.controls_layout.addStretch()  # Push controls to left

        # Input and messaging (below video)
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

        # Set the main layout
        self.setLayout(self.layout)

        # Connect signals
        self.send_button.clicked.connect(self.send_message)
        self.input_field.returnPressed.connect(self.send_message)
        self.open_file_button.clicked.connect(self.open_file)
        self.pause_button.clicked.connect(self.pause_media)
        self.stop_button.clicked.connect(self.stop_media)
        self.fullscreen_button.clicked.connect(self.toggle_fullscreen)

        # Initial positioning of controls
        self.adjust_controls_position()

    def send_message(self):
        """Send the message from input_field to the server."""
        message = self.input_field.text().strip()
        if message:
            try:
                Protocol.send(self.client_socket, message)
                self.input_field.clear()
            except Exception as e:
                self.response_box.append(f"Error sending message: {e}")

    def listen_for_responses(self):
        """Listen for server responses in a separate thread."""
        while True:
            try:
                response = Protocol.receive(self.client_socket)
                if not response:
                    self.response_box.append("Disconnected from server.")
                    break
                self.response_box.append(f"Server: {response}")
            except Exception as e:
                self.response_box.append(f"Error receiving response: {e}")
                break

    def start_listening(self):
        """Start a thread to listen for server responses."""
        self.listen_thread = Thread(target=self.listen_for_responses, daemon=True)
        self.listen_thread.start()

    def open_file(self):
        """Open a file dialog to select a local media file."""
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Media File", "",
                                                   "Media Files (*.mp4 *.avi *.mkv *.mp3 *.wav)")
        if file_path:
            self.response_box.append(f"Selected file: {file_path}")
            self.player.playlist_clear()
            self.player.playlist_append(file_path)
            self.player.playlist_pos = 0
            self.progress_slider.setValue(0)
            self.progress_slider.setEnabled(True)  # Enable progress bar

    def pause_media(self):
        """Pause or unpause the loaded media."""
        if self.player.pause:
            self.player.pause = False
            self.response_box.append("Resumed media.")
        else:
            self.player.pause = True
            self.response_box.append("Paused media.")

    def stop_media(self):
        """Stop the loaded media."""
        self.player.stop()
        self.response_box.append("Stopped media.")
        self.progress_slider.setValue(0)
        self.progress_slider.setEnabled(False)  # Disable progress bar

    def set_volume(self, value):
        """Set the volume based on slider value."""
        self.player.volume = value
        self.response_box.append(f"Volume set to {value}%")

    def update_progress(self):
        """Update the progress slider based on current playback position."""
        if self.player.duration and self.player.time_pos:
            progress = (self.player.time_pos / self.player.duration) * 100
            self.progress_slider.blockSignals(True)
            self.progress_slider.setValue(int(progress))
            self.progress_slider.blockSignals(False)

    def start_seeking(self):
        """Prepare for seeking when slider is pressed."""
        self.seeking = True

    def seek_to_position(self, value):
        """Seek to a position in the video based on slider value."""
        if self.player.duration:
            seek_time = (value / 100) * self.player.duration
            self.player.time_pos = seek_time
            self.response_box.append(f"Seeking to {value}%")

    def toggle_fullscreen(self):
        """Toggle fullscreen mode."""
        if self.isFullScreen():
            self.showNormal()
            self.fullscreen_button.setText("Fullscreen")
        else:
            self.showFullScreen()
            self.fullscreen_button.setText("Exit Fullscreen")
        self.adjust_controls_position()

    def adjust_controls_position(self):
        """Adjust controls position when window size changes."""
        # Position controls at the bottom of the video frame area
        video_rect = self.video_frame.geometry()
        controls_height = self.controls_widget.height()
        self.controls_widget.setGeometry(
            video_rect.left(),
            video_rect.bottom() - controls_height,
            video_rect.width(),
            controls_height
        )

    def mpv_log(self, loglevel, component, message):
        """Log MPV output to the response box (optional)."""
        self.response_box.append(f"[MPV {loglevel}] {component}: {message}")

    def keyPressEvent(self, event):
        """Handle key press events, e.g., spacebar to toggle pause."""
        if event.key() == Qt.Key.Key_Space:
            self.pause_media()
            event.accept()
        else:
            super().keyPressEvent(event)

    def wheelEvent(self, event):
        """Handle mouse wheel events for volume and progress sliders."""
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
        """Handle mouse click on progress slider for seeking."""
        if self.progress_slider.isEnabled() and self.progress_slider.underMouse():
            pos = self.progress_slider.mapFromGlobal(event.globalPosition().toPoint())
            value = self.progress_slider.minimum() + (self.progress_slider.maximum() - self.progress_slider.minimum()) * pos.x() / self.progress_slider.width()
            value = min(max(int(value), 0), 100)  # Clamp to 0-100
            self.seek_to_position(value)
        super().mouseReleaseEvent(event)

    def resizeEvent(self, event):
        """Adjust controls position on window resize."""
        self.adjust_controls_position()
        super().resizeEvent(event)

    def closeEvent(self, event):
        """Handle window close event to cleanly close the socket and terminate MPV."""
        self.progress_timer.stop()
        self.player.terminate()
        self.client_socket.close()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = ClientGUI(None)  # Replace None with a real socket for actual use
    sys.exit(app.exec())
