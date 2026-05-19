"""
Screen Recorder Application.
A user-friendly screen recorder built with customtkinter and OpenCV.
"""

import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Final, Self

import customtkinter as ctk
import cv2
import numpy as np
from PIL import ImageGrab
from screeninfo import get_monitors

# Constants
DEFAULT_OUTPUT_DIR: Final[Path] = Path.home() / "Videos" / "ScreenRecordings"
FPS: Final[int] = 20
FOURCC: Final[int] = cv2.VideoWriter_fourcc(*"mp4v")  # type: ignore


class ScreenRecorder:
    """Handles the screen recording logic in a separate thread."""

    def __init__(self, output_dir: Path) -> None:
        """
        Initialize the recorder.

        Args:
            output_dir: The directory where recordings will be saved.
        """
        self.output_dir: Path = output_dir
        self.is_recording: bool = False
        self._stop_event: threading.Event = threading.Event()
        self._thread: threading.Thread | None = None
        self.current_filename: str | None = None

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def start(self) -> None:
        """Start the recording thread."""
        if self.is_recording:
            return

        self.is_recording = True
        self._stop_event.clear()
        
        timestamp: str = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.current_filename = f"recording_{timestamp}.mp4"
        output_path: Path = self.output_dir / self.current_filename

        self._thread = threading.Thread(
            target=self._record_loop, args=(output_path,), daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop the recording thread."""
        if not self.is_recording:
            return

        self.is_recording = False
        self._stop_event.set()
        if self._thread:
            self._thread.join()

    def _record_loop(self, output_path: Path) -> None:
        """
        Main recording loop.

        Args:
            output_path: Path to save the video file.
        """
        # Get primary monitor resolution
        monitor = get_monitors()[0]
        screen_size: tuple[int, int] = (monitor.width, monitor.height)

        out = cv2.VideoWriter(
            str(output_path), FOURCC, FPS, screen_size
        )

        try:
            while not self._stop_event.is_set():
                # Capture screen
                img = ImageGrab.grab(bbox=(0, 0, screen_size[0], screen_size[1]))
                frame = np.array(img)
                
                # Convert RGB to BGR (OpenCV uses BGR)
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

                # Write frame
                out.write(frame)
                
                # Control FPS (simple sleep)
                time.sleep(1 / FPS)
        finally:
            out.release()


class RecorderApp(ctk.CTk):
    """Main Application GUI."""

    def __init__(self) -> None:
        """Initialize the GUI."""
        super().__init__()

        self.title("Gemini Screen Recorder")
        self.geometry("400x350")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.recorder: ScreenRecorder = ScreenRecorder(DEFAULT_OUTPUT_DIR)
        self.start_time: float = 0.0

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Create and arrange UI components."""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure((0, 1, 2, 3, 4), weight=1)

        # Header
        self.label_title = ctk.CTkLabel(
            self, text="Screen Recorder", font=ctk.CTkFont(size=24, weight="bold")
        )
        self.label_title.grid(row=0, column=0, padx=20, pady=(20, 10))

        # Status Label
        self.label_status = ctk.CTkLabel(
            self, text=f"Ready to record\nSaving to: {self.recorder.output_dir.name}",
            font=ctk.CTkFont(size=14)
        )
        self.label_status.grid(row=1, column=0, padx=20, pady=10)

        # Timer Label
        self.label_timer = ctk.CTkLabel(
            self, text="00:00:00", font=ctk.CTkFont(size=20, weight="bold")
        )
        self.label_timer.grid(row=2, column=0, padx=20, pady=10)

        # Control Buttons
        self.btn_start = ctk.CTkButton(
            self, text="Start Recording", fg_color="green", hover_color="darkgreen",
            command=self._on_start
        )
        self.btn_start.grid(row=3, column=0, padx=20, pady=10)

        self.btn_stop = ctk.CTkButton(
            self, text="Stop Recording", fg_color="red", hover_color="darkred",
            command=self._on_stop, state="disabled"
        )
        self.btn_stop.grid(row=4, column=0, padx=20, pady=10)

    def _on_start(self) -> None:
        """Handle start button click."""
        self.btn_start.configure(state="disabled")
        self.label_status.configure(text="Starting in 3...")
        self.update()
        
        # Simple countdown
        for i in range(2, 0, -1):
            time.sleep(1)
            self.label_status.configure(text=f"Starting in {i}...")
            self.update()
        
        time.sleep(1)
        self.recorder.start()
        self.start_time = time.time()
        
        self.btn_stop.configure(state="normal")
        self.label_status.configure(text="Recording...")
        self._update_timer()

    def _on_stop(self) -> None:
        """Handle stop button click."""
        self.recorder.stop()
        self.btn_stop.configure(state="disabled")
        self.btn_start.configure(state="normal")
        self.label_status.configure(
            text=f"Saved: {self.recorder.current_filename}"
        )

    def _update_timer(self) -> None:
        """Update the duration timer on the GUI."""
        if self.recorder.is_recording:
            elapsed: float = time.time() - self.start_time
            hours, rem = divmod(int(elapsed), 3600)
            minutes, seconds = divmod(rem, 60)
            self.label_timer.configure(text=f"{hours:02}:{minutes:02}:{seconds:02}")
            self.after(1000, self._update_timer)


if __name__ == "__main__":
    app = RecorderApp()
    app.mainloop()
