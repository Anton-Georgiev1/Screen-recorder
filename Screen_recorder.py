"""
Screen Recorder Application.
A user-friendly screen recorder built with customtkinter, OpenCV, and SoundDevice.
"""

import threading
import time
import wave
from datetime import datetime
from pathlib import Path
from typing import Final

import customtkinter as ctk
import cv2
import numpy as np
import sounddevice as sd
from moviepy import VideoFileClip, AudioFileClip
from PIL import ImageGrab
from screeninfo import get_monitors

# Constants
DEFAULT_OUTPUT_DIR: Final[Path] = Path.home() / "Videos" / "ScreenRecordings"
FPS: Final[int] = 20
SAMPLE_RATE: Final[int] = 44100
CHANNELS: Final[int] = 2

FORMATS: Final[dict[str, str]] = {
    "mp4": "mp4v",
    "avi": "XVID",
}


class ScreenRecorder:
    """Handles the screen and audio recording logic."""

    def __init__(self, output_dir: Path) -> None:
        """
        Initialize the recorder.

        Args:
            output_dir: The directory where recordings will be saved.
        """
        self.output_dir: Path = output_dir
        self.is_recording: bool = False
        self._stop_event: threading.Event = threading.Event()
        self._video_thread: threading.Thread | None = None
        self._audio_thread: threading.Thread | None = None
        self.current_filename: str | None = None
        self.video_format: str = "mp4"
        self.record_audio: bool = False

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def start(self, video_format: str = "mp4", record_audio: bool = False) -> None:
        """
        Start the recording threads.

        Args:
            video_format: The format of the video file (e.g., 'mp4', 'avi').
            record_audio: Whether to record audio.
        """
        if self.is_recording:
            return

        self.is_recording = True
        self.video_format = video_format
        self.record_audio = record_audio
        self._stop_event.clear()
        
        timestamp: str = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.current_filename = f"recording_{timestamp}.{self.video_format}"
        
        # Temporary files for merging
        self._temp_video = self.output_dir / f"temp_video_{timestamp}.avi"
        self._temp_audio = self.output_dir / f"temp_audio_{timestamp}.wav"

        self._video_thread = threading.Thread(
            target=self._record_video, args=(self._temp_video,), daemon=True
        )
        self._video_thread.start()

        if self.record_audio:
            self._audio_thread = threading.Thread(
                target=self._record_audio_loop, args=(self._temp_audio,), daemon=True
            )
            self._audio_thread.start()

    def stop(self) -> None:
        """Stop the recording and merge files."""
        if not self.is_recording:
            return

        self.is_recording = False
        self._stop_event.set()
        
        if self._video_thread:
            self._video_thread.join()
        if self._audio_thread:
            self._audio_thread.join()

        self._finalize_recording()

    def _record_video(self, output_path: Path) -> None:
        """Video recording loop."""
        monitor = get_monitors()[0]
        screen_size: tuple[int, int] = (monitor.width, monitor.height)
        
        # Always use AVI for temp video to ensure compatibility with OpenCV before merging
        fourcc = cv2.VideoWriter_fourcc(*"XVID")
        out = cv2.VideoWriter(str(output_path), fourcc, FPS, screen_size)

        frame_duration = 1.0 / FPS
        
        try:
            while not self._stop_event.is_set():
                start_time = time.time()
                
                img = ImageGrab.grab(bbox=(0, 0, screen_size[0], screen_size[1]))
                frame = np.array(img)
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                out.write(frame)
                
                # Precise sleep to maintain 1.0x speed
                elapsed = time.time() - start_time
                sleep_time = max(0, frame_duration - elapsed)
                time.sleep(sleep_time)
        finally:
            out.release()

    def _record_audio_loop(self, output_path: Path) -> None:
        """Audio recording loop."""
        audio_data = []

        def callback(indata, frames, time, status):
            if status:
                print(status)
            audio_data.append(indata.copy())

        with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, callback=callback):
            while not self._stop_event.is_set():
                time.sleep(0.1)

        if audio_data:
            full_audio = np.concatenate(audio_data, axis=0)
            with wave.open(str(output_path), 'wb') as wf:
                wf.setnchannels(CHANNELS)
                wf.setsampwidth(2) # 16-bit
                wf.setframerate(SAMPLE_RATE)
                wf.writeframes((full_audio * 32767).astype(np.int16).tobytes())

    def _finalize_recording(self) -> None:
        """Merge audio and video into the final file."""
        final_path = self.output_dir / self.current_filename
        
        try:
            with VideoFileClip(str(self._temp_video)) as video_clip:
                if self.record_audio and self._temp_audio.exists():
                    with AudioFileClip(str(self._temp_audio)) as audio_clip:
                        final_clip = video_clip.with_audio(audio_clip)
                        final_clip.write_videofile(
                            str(final_path), 
                            codec="libx264", 
                            audio_codec="aac", 
                            logger=None
                        )
                else:
                    if self.video_format == "mp4":
                        video_clip.write_videofile(
                            str(final_path), 
                            codec="libx264", 
                            logger=None
                        )
                    else:
                        # For AVI, if no audio, we can just rename/move if it's already XVID
                        # But to be safe and ensure format consistency, let's write it
                        video_clip.write_videofile(
                            str(final_path), 
                            codec="png", # High quality for AVI
                            logger=None
                        )
        except Exception as e:
            print(f"Error during finalization: {e}")
        finally:
            # Give OS a moment to release handles
            time.sleep(0.5)
            if self._temp_video.exists():
                try:
                    self._temp_video.unlink()
                except Exception as e:
                    print(f"Could not delete temp video: {e}")
            if self._temp_audio.exists():
                try:
                    self._temp_audio.unlink()
                except Exception as e:
                    print(f"Could not delete temp audio: {e}")


class RecorderApp(ctk.CTk):
    """Main Application GUI."""

    def __init__(self) -> None:
        """Initialize the GUI."""
        super().__init__()

        self.title("Screen_recorder")
        self.geometry("500x550")
        self.resizable(False, False) # Disable maximize button

        self.output_path_var = ctk.StringVar(value=str(DEFAULT_OUTPUT_DIR))
        self.format_var = ctk.StringVar(value="mp4")
        self.audio_var = ctk.BooleanVar(value=False)
        self.theme_var = ctk.StringVar(value="Dark")
        
        self.recorder: ScreenRecorder = ScreenRecorder(Path(self.output_path_var.get()))
        self.start_time: float = 0.0

        self._setup_ui()
        self._apply_theme()

    def _setup_ui(self) -> None:
        """Create and arrange UI components."""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure((0, 1, 2, 3, 4, 5, 6, 7, 8), weight=1)

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

        # Options Frame
        self.frame_options = ctk.CTkFrame(self)
        self.frame_options.grid(row=2, column=0, padx=20, pady=5, sticky="ew")
        self.frame_options.grid_columnconfigure((0, 1), weight=1)

        # Format Selection
        self.label_format = ctk.CTkLabel(self.frame_options, text="Format:")
        self.label_format.grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.option_format = ctk.CTkOptionMenu(
            self.frame_options, values=list(FORMATS.keys()), variable=self.format_var
        )
        self.option_format.grid(row=0, column=1, padx=10, pady=5, sticky="e")

        # Audio Toggle
        self.check_audio = ctk.CTkCheckBox(self.frame_options, text="Record Audio", variable=self.audio_var)
        self.check_audio.grid(row=1, column=0, columnspan=2, padx=10, pady=5, sticky="w")

        # Theme Toggle
        self.label_theme = ctk.CTkLabel(self.frame_options, text="Theme:")
        self.label_theme.grid(row=2, column=0, padx=10, pady=5, sticky="w")
        self.option_theme = ctk.CTkOptionMenu(
            self.frame_options, values=["Light", "Dark"], variable=self.theme_var, command=self._apply_theme
        )
        self.option_theme.grid(row=2, column=1, padx=10, pady=5, sticky="e")

        # Status Label
        self.label_status = ctk.CTkLabel(
            self, text="Ready to record",
            font=ctk.CTkFont(size=14)
        )
        self.label_status.grid(row=4, column=0, padx=20, pady=10)

        # Timer Label
        self.label_timer = ctk.CTkLabel(
            self, text="00:00:00", font=ctk.CTkFont(size=20, weight="bold")
        )
        self.label_timer.grid(row=5, column=0, padx=20, pady=10)

        # Control Buttons
        self.btn_start = ctk.CTkButton(
            self, text="Start Recording", fg_color="green", hover_color="darkgreen",
            command=self._on_start
        )
        self.btn_start.grid(row=6, column=0, padx=20, pady=10)

        self.btn_stop = ctk.CTkButton(
            self, text="Stop Recording", fg_color="red", hover_color="darkred",
            command=self._on_stop, state="disabled"
        )
        self.btn_stop.grid(row=7, column=0, padx=20, pady=10)

    def _apply_theme(self, theme: str | None = None) -> None:
        """Apply selected theme."""
        ctk.set_appearance_mode(self.theme_var.get())

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
        self.check_audio.configure(state="disabled")
        
        self.label_status.configure(text="Starting in 3...")
        self.update()
        
        for i in range(2, 0, -1):
            time.sleep(1)
            self.label_status.configure(text=f"Starting in {i}...")
            self.update()
        
        time.sleep(1)
        self.recorder.start(video_format=self.format_var.get(), record_audio=self.audio_var.get())
        self.start_time = time.time()
        
        self.btn_stop.configure(state="normal")
        self.label_status.configure(text="Recording...")
        self._update_timer()

    def _on_stop(self) -> None:
        """Handle stop button click."""
        self.label_status.configure(text="Saving and merging... please wait.")
        self.update()
        
        self.recorder.stop()
        
        self.btn_stop.configure(state="disabled")
        self.btn_start.configure(state="normal")
        self.btn_browse.configure(state="normal")
        self.option_format.configure(state="normal")
        self.check_audio.configure(state="normal")
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

