"""
Screen Recorder Application.
A user-friendly screen recorder built with customtkinter, OpenCV, and soundcard.
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
import soundcard as sc
from moviepy import VideoFileClip, AudioFileClip, CompositeAudioClip
from PIL import ImageGrab
from screeninfo import get_monitors

# Constants
DEFAULT_OUTPUT_DIR: Final[Path] = Path.home() / "Videos" / "ScreenRecordings"
FPS: Final[int] = 20
SAMPLE_RATE: Final[int] = 44100

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
        self._audio_threads: list[threading.Thread] = []
        
        self.current_filename: str | None = None
        self.video_format: str = "mp4"
        self.audio_source: str = "None"
        
        self._temp_video: Path | None = None
        self._temp_mic: Path | None = None
        self._temp_sys: Path | None = None

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def start(self, video_format: str = "mp4", audio_source: str = "None") -> None:
        """
        Start the recording threads.

        Args:
            video_format: The format of the video file (e.g., 'mp4', 'avi').
            audio_source: Type of audio to record ('None', 'Microphone', 'System Audio', 'Mic + System').
        """
        if self.is_recording:
            return

        self.is_recording = True
        self.video_format = video_format
        self.audio_source = audio_source
        self._stop_event.clear()
        
        timestamp: str = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.current_filename = f"recording_{timestamp}.{self.video_format}"
        
        # Temporary files for merging
        self._temp_video = self.output_dir / f"temp_video_{timestamp}.avi"
        self._temp_mic = self.output_dir / f"temp_mic_{timestamp}.wav"
        self._temp_sys = self.output_dir / f"temp_sys_{timestamp}.wav"
        self._audio_threads = []

        # Start Video Thread
        self._video_thread = threading.Thread(
            target=self._record_video, args=(self._temp_video,), daemon=True
        )
        self._video_thread.start()

        # Start Audio Thread(s) depending on selection
        if self.audio_source in ["Microphone", "Mic + System"]:
            t_mic = threading.Thread(
                target=self._record_audio_loop, args=(self._temp_mic, "mic"), daemon=True
            )
            self._audio_threads.append(t_mic)
            t_mic.start()
            
        if self.audio_source in ["System Audio", "Mic + System"]:
            t_sys = threading.Thread(
                target=self._record_audio_loop, args=(self._temp_sys, "sys"), daemon=True
            )
            self._audio_threads.append(t_sys)
            t_sys.start()

    def stop(self) -> None:
        """Stop the recording and merge files."""
        if not self.is_recording:
            return

        self.is_recording = False
        self._stop_event.set()
        
        if self._video_thread:
            self._video_thread.join()
        for t in self._audio_threads:
            t.join()

        self._finalize_recording()

    def _record_video(self, output_path: Path) -> None:
        """Video recording loop."""
        try:
            monitor = get_monitors()[0]
            bbox = (0, 0, monitor.width, monitor.height)
        except Exception:
            bbox = None
        
        # Always use AVI for temp video to ensure compatibility with OpenCV before merging
        fourcc = cv2.VideoWriter_fourcc(*"XVID")
        out = None
        frame_duration = 1.0 / FPS
        
        try:
            while not self._stop_event.is_set():
                start_time = time.time()
                
                img = ImageGrab.grab(bbox=bbox) if bbox else ImageGrab.grab()
                frame = np.array(img)
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                
                # Wait to initialize VideoWriter until we know the EXACT frame size 
                # (Prevents silent OpenCV failures on displays with DPI scaling > 100%)
                if out is None:
                    height, width, _ = frame.shape
                    out = cv2.VideoWriter(str(output_path), fourcc, FPS, (width, height))
                    
                out.write(frame)
                
                # Precise sleep to maintain 1.0x speed
                elapsed = time.time() - start_time
                sleep_time = max(0, frame_duration - elapsed)
                time.sleep(sleep_time)
        finally:
            if out is not None:
                out.release()

    def _record_audio_loop(self, output_path: Path, audio_type: str) -> None:
        """Audio recording loop supporting both Microphone and System Loopback."""
        try:
            if audio_type == "sys":
                # Find the default speaker and grab its loopback stream
                speaker = sc.default_speaker()
                mic = sc.get_microphone(id=str(speaker.id), include_loopback=True)
            else:
                # Grab standard default microphone
                mic = sc.default_microphone()
                
            audio_data = []
            
            # Soundcard records in float32 format
            with mic.recorder(samplerate=SAMPLE_RATE) as recorder:
                while not self._stop_event.is_set():
                    # Record in 0.1-second chunks
                    data = recorder.record(numframes=SAMPLE_RATE // 10)
                    audio_data.append(data)
                    
            if audio_data:
                full_audio = np.concatenate(audio_data, axis=0)
                
                # Ensure 2D array (samples, channels)
                if len(full_audio.shape) == 1:
                    full_audio = np.expand_dims(full_audio, axis=1)
                    
                actual_channels = full_audio.shape[1]
                
                # Convert from Float32 to Int16 for standard WAV format
                full_audio = np.clip(full_audio, -1.0, 1.0)
                full_audio = (full_audio * 32767).astype(np.int16)
                
                with wave.open(str(output_path), 'wb') as wf:
                    wf.setnchannels(actual_channels)
                    wf.setsampwidth(2) # 16-bit
                    wf.setframerate(SAMPLE_RATE)
                    wf.writeframes(full_audio.tobytes())
                    
        except Exception as e:
            print(f"Error recording {audio_type} audio: {e}")

    def _finalize_recording(self) -> None:
        """Merge audio (mic/sys) and video into the final file."""
        final_path = self.output_dir / self.current_filename
        
        try:
            with VideoFileClip(str(self._temp_video)) as video_clip:
                audio_clips = []
                
                # Check for recorded audio tracks
                if self.audio_source in ["Microphone", "Mic + System"] and self._temp_mic and self._temp_mic.exists():
                    audio_clips.append(AudioFileClip(str(self._temp_mic)))
                    
                if self.audio_source in ["System Audio", "Mic + System"] and self._temp_sys and self._temp_sys.exists():
                    audio_clips.append(AudioFileClip(str(self._temp_sys)))
                
                # Mix and Attach Audio
                if audio_clips:
                    if len(audio_clips) > 1:
                        final_audio = CompositeAudioClip(audio_clips)
                    else:
                        final_audio = audio_clips[0]
                        
                    final_clip = video_clip.with_audio(final_audio)
                    final_clip.write_videofile(
                        str(final_path), 
                        codec="libx264", 
                        audio_codec="aac", 
                        logger=None
                    )
                    
                    for ac in audio_clips:
                        ac.close()
                    if len(audio_clips) > 1:
                        final_audio.close()
                else:
                    # Write Video Only
                    if self.video_format == "mp4":
                        video_clip.write_videofile(str(final_path), codec="libx264", logger=None)
                    else:
                        video_clip.write_videofile(str(final_path), codec="png", logger=None)
                        
        except Exception as e:
            print(f"Error during finalization: {e}")
        finally:
            # Clean up all temporary files safely
            time.sleep(0.5)
            for temp_file in [self._temp_video, self._temp_mic, self._temp_sys]:
                if temp_file is not None and temp_file.exists():
                    try:
                        temp_file.unlink()
                    except Exception as e:
                        print(f"Could not delete temp file {temp_file.name}: {e}")


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
        self.audio_source_var = ctk.StringVar(value="System Audio")
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

        # Audio Selection
        self.label_audio = ctk.CTkLabel(self.frame_options, text="Audio Source:")
        self.label_audio.grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.option_audio = ctk.CTkOptionMenu(
            self.frame_options, 
            values=["None", "Microphone", "System Audio", "Mic + System"], 
            variable=self.audio_source_var
        )
        self.option_audio.grid(row=1, column=1, padx=10, pady=5, sticky="e")

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
        self.option_audio.configure(state="disabled")
        
        self.countdown = 3
        self._countdown_step()

    def _countdown_step(self) -> None:
        """Non-blocking countdown before the recording starts."""
        if self.countdown > 0:
            self.label_status.configure(text=f"Starting in {self.countdown}...")
            self.countdown -= 1
            self.after(1000, self._countdown_step)
        else:
            self.label_status.configure(text="Recording...")
            self.recorder.start(
                video_format=self.format_var.get(), 
                audio_source=self.audio_source_var.get()
            )
            self.start_time = time.time()
            self.btn_stop.configure(state="normal")
            self._update_timer()

    def _on_stop(self) -> None:
        """Handle stop button click."""
        self.label_status.configure(text="Saving and merging... please wait.")
        self.btn_stop.configure(state="disabled")
        self.update()
        
        # Run saving logic in a background thread to prevent GUI freeze
        threading.Thread(target=self._stop_recording_thread, daemon=True).start()

    def _stop_recording_thread(self) -> None:
        """Run recorder stop functionality in the background."""
        self.recorder.stop()
        self.after(0, self._on_stop_finished)

    def _on_stop_finished(self) -> None:
        """Re-enable elements once merging completely finishes."""
        self.btn_start.configure(state="normal")
        self.btn_browse.configure(state="normal")
        self.option_format.configure(state="normal")
        self.option_audio.configure(state="normal")
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