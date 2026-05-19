"""
Screen Recorder Application.
A user-friendly screen recorder built with customtkinter and OpenCV.
"""

import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Final

import customtkinter as ctk
import cv2
import numpy as np
from PIL import ImageGrab
from screeninfo import get_monitors

# Constants
DEFAULT_OUTPUT_DIR: Final[Path] = Path.home() / "Videos" / "ScreenRecordings"
FPS: Final[int] = 20

FORMATS: Final[dict[str, str]] = {
    "mp4": "mp4v",
    "avi": "XVID",
}


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
        self.video_format: str = "mp4"

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def start(self, video_format: str = "mp4") -> None:
        """
        Start the recording thread.

        Args:
            video_format: The format of the video file (e.g., 'mp4', 'avi').
        """
        if self.is_recording:
            return

        self.is_recording = True
        self.video_format = video_format
        self._stop_event.clear()
        
        timestamp: str = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.current_filename = f"recording_{timestamp}.{self.video_format}"
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

        fourcc_code = FORMATS.get(self.video_format, "mp4v")
        fourcc = cv2.VideoWriter_fourcc(*fourcc_code) # type: ignore

        out = cv2.VideoWriter(
            str(output_path), fourcc, FPS, screen_size
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
        self.geometry("500x450")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.output_path_var = ctk.StringVar(value=str(DEFAULT_OUTPUT_DIR))
        self.format_var = ctk.StringVar(value="mp4")
        self.recorder: ScreenRecorder = ScreenRecorder(Path(self.output_path_var.get()))
        self.start_time: float = 0.0

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Create and arrange UI components."""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure((0, 1, 2, 3, 4, 5, 6), weight=1)

        # Header
        self.label_title = ctk.CTkLabel(
            self, text="Screen Recorder", font=ctk.CTkFont(size=24, weight="bold")
        )
        self.label_title.grid(row=0, column=0, padx=20, pady=(20, 10))

        # Folder Selection
        self.frame_folder = ctk.CTkFrame(self)
        self.frame_folder.grid(row=1, column=0, padx=20, pady=5, sticky="ew")
        self.frame_folder.grid_columnconfigure(0, weight=1)

        self.entry_path = ctk.CTkEntry(self.frame_folder, textvariable=self.output_path_var, state="readonly")
        self.entry_path.grid(row=0, column=0, padx=(10, 5), pady=10, sticky="ew")

        self.btn_browse = ctk.CTkButton(self.frame_folder, text="Browse", width=80, command=self._on_choose_folder)
        self.btn_browse.grid(row=0, column=1, padx=(5, 10), pady=10)

        # Format Selection
        self.frame_format = ctk.CTkFrame(self)
        self.frame_format.grid(row=2, column=0, padx=20, pady=5, sticky="ew")
        
        self.label_format = ctk.CTkLabel(self.frame_format, text="Video Format:")
        self.label_format.grid(row=0, column=0, padx=10, pady=10)

        self.option_format = ctk.CTkOptionMenu(
            self.frame_format, values=list(FORMATS.keys()), variable=self.format_var
        )
        self.option_format.grid(row=0, column=1, padx=10, pady=10)

        # Status Label
        self.label_status = ctk.CTkLabel(
            self, text="Ready to record",
            font=ctk.CTkFont(size=14)
        )
        self.label_status.grid(row=3, column=0, padx=20, pady=10)

        # Timer Label
        self.label_timer = ctk.CTkLabel(
            self, text="00:00:00", font=ctk.CTkFont(size=20, weight="bold")
        )
        self.label_timer.grid(row=4, column=0, padx=20, pady=10)

        # Control Buttons
        self.btn_start = ctk.CTkButton(
            self, text="Start Recording", fg_color="green", hover_color="darkgreen",
            command=self._on_start
        )
        self.btn_start.grid(row=5, column=0, padx=20, pady=10)

        self.btn_stop = ctk.CTkButton(
            self, text="Stop Recording", fg_color="red", hover_color="darkred",
            command=self._on_stop, state="disabled"
        )
        self.btn_stop.grid(row=6, column=0, padx=20, pady=10)

    def _on_choose_folder(self) -> None:
        """Open folder dialog to select output directory."""
        folder_selected = ctk.filedialog.askdirectory()
        if folder_selected:
            self.output_path_var.set(folder_selected)
            self.recorder.output_dir = Path(folder_selected)
            self.recorder.output_dir.mkdir(parents=True, exist_ok=True)

    def _on_start(self) -> None:
        """Handle start button click."""
        self.btn_start.configure(state="disabled")
        self.btn_browse.configure(state="disabled")
        self.option_format.configure(state="disabled")
        
        self.label_status.configure(text="Starting in 3...")
        self.update()
        
        # Simple countdown
        for i in range(2, 0, -1):
            time.sleep(1)
            self.label_status.configure(text=f"Starting in {i}...")
            self.update()
        
        time.sleep(1)
        self.recorder.start(video_format=self.format_var.get())
        self.start_time = time.time()
        
        self.btn_stop.configure(state="normal")
        self.label_status.configure(text="Recording...")
        self._update_timer()

    def _on_stop(self) -> None:
        """Handle stop button click."""
        self.recorder.stop()
        self.btn_stop.configure(state="disabled")
        self.btn_start.configure(state="normal")
        self.btn_browse.configure(state="normal")
        self.option_format.configure(state="normal")
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
