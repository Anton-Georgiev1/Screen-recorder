"""
Screen Recorder Application.
A user-friendly screen recorder built with customtkinter, OpenCV, and sounddevice.
Features Fast FFmpeg saving and a Pause/Resume function.
"""

import os
import subprocess
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
import imageio_ffmpeg
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
    """Handles the screen and audio recording logic."""

    def __init__(self, output_dir: Path) -> None:
        """
        Initialize the recorder.
        """
        self.output_dir: Path = output_dir
        self.is_recording: bool = False
        self._stop_event: threading.Event = threading.Event()
        self._pause_event: threading.Event = threading.Event()
        
        self._video_thread: threading.Thread | None = None
        self._audio_thread: threading.Thread | None = None
        
        self.current_filename: str | None = None
        self.video_format: str = "mp4"
        self.audio_source: str = "None"
        
        self._temp_video: Path | None = None
        self._temp_mic: Path | None = None

        self.output_dir.mkdir(parents=True, exist_ok=True)

    @property
    def is_paused(self) -> bool:
        return self._pause_event.is_set()

    def pause(self) -> None:
        self._pause_event.set()

    def resume(self) -> None:
        self._pause_event.clear()

    def start(self, video_format: str = "mp4", audio_source: str = "None") -> None:
        """Start the recording threads."""
        if self.is_recording:
            return

        self.is_recording = True
        self.video_format = video_format
        self.audio_source = audio_source
        self._stop_event.clear()
        self._pause_event.clear()
        
        timestamp: str = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.current_filename = f"recording_{timestamp}.{self.video_format}"
        
        # Temporary files for merging
        self._temp_video = self.output_dir / f"temp_video_{timestamp}.avi"
        self._temp_mic = self.output_dir / f"temp_mic_{timestamp}.wav"

        # Start Video Thread
        self._video_thread = threading.Thread(
            target=self._record_video, args=(self._temp_video,), daemon=True
        )
        self._video_thread.start()

        # Start Audio Thread
        if self.audio_source == "Microphone":
            self._audio_thread = threading.Thread(
                target=self._record_audio_loop, args=(self._temp_mic,), daemon=True
            )
            self._audio_thread.start()

    def stop(self) -> None:
        """Stop the recording and trigger the fast merge."""
        if not self.is_recording:
            return

        self.is_recording = False
        self._pause_event.clear() # Ensure threads aren't stuck sleeping
        self._stop_event.set()
        
        if self._video_thread:
            self._video_thread.join(timeout=2.0)
        if self._audio_thread:
            self._audio_thread.join(timeout=2.0)

        self._finalize_recording()

    def _record_video(self, output_path: Path) -> None:
        """Video recording loop equipped with Pause support."""
        try:
            monitor = get_monitors()[0]
            bbox = (0, 0, monitor.width, monitor.height)
        except Exception:
            bbox = None
        
        fourcc = cv2.VideoWriter_fourcc(*"XVID")
        out = None
        frame_duration = 1.0 / FPS
        
        try:
            next_frame_time = time.time()
            while not self._stop_event.is_set():
                
                # If Paused, Idle and keep next_frame_time fresh so it doesn't burst frames when unpaused
                if self._pause_event.is_set():
                    time.sleep(0.1)
                    next_frame_time = time.time() 
                    continue
                
                img = ImageGrab.grab(bbox=bbox) if bbox else ImageGrab.grab()
                frame = np.array(img)
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                
                if out is None:
                    height, width, _ = frame.shape
                    out = cv2.VideoWriter(str(output_path), fourcc, FPS, (width, height))
                    
                out.write(frame)
                
                next_frame_time += frame_duration
                sleep_time = next_frame_time - time.time()
                
                if sleep_time > 0:
                    time.sleep(sleep_time)
                else:
                    # Reset if falling slightly behind to prevent catch-up jitter
                    next_frame_time = time.time()
        finally:
            if out is not None:
                out.release()

    def _record_audio_loop(self, output_path: Path) -> None:
        """Audio recording loop equipped with Pause support."""
        audio_data = []

        def callback(indata, frames, time_info, status):
            # Only record the audio chunk if we are not paused
            if not self._pause_event.is_set():
                audio_data.append(indata.copy())

        try:
            try:
                stream = sd.InputStream(samplerate=48000, dtype='int16', callback=callback)
            except Exception:
                stream = sd.InputStream(dtype='int16', callback=callback)

            with stream:
                channels = stream.channels
                samplerate = int(stream.samplerate)
                
                while not self._stop_event.is_set():
                    time.sleep(0.1)

            if audio_data:
                full_audio = np.concatenate(audio_data, axis=0)
                
                with wave.open(str(output_path), 'wb') as wf:
                    wf.setnchannels(channels)
                    wf.setsampwidth(2) # 16-bit
                    wf.setframerate(samplerate)
                    wf.writeframes(full_audio.tobytes())
                    
        except Exception as e:
            print(f"Error recording audio: {e}")

    def _finalize_recording(self) -> None:
        """Fast FFmpeg merger (Extremely fast, skips python re-encoding entirely)."""
        final_path = self.output_dir / self.current_filename
        
        try:
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
            cmd = [ffmpeg_exe, "-y"]
            
            cmd.extend(["-i", str(self._temp_video)])
            
            has_audio = self.audio_source == "Microphone" and self._temp_mic and self._temp_mic.exists()
            if has_audio:
                cmd.extend(["-i", str(self._temp_mic)])
                
            # For MP4 we encode fast, for AVI we just stream-copy making it instant
            if self.video_format == "mp4":
                cmd.extend(["-c:v", "libx264", "-preset", "superfast", "-crf", "23"])
            else:
                cmd.extend(["-c:v", "copy"])
                
            if has_audio:
                if self.video_format == "mp4":
                    cmd.extend(["-c:a", "aac", "-b:a", "320k"])
                else:
                    cmd.extend(["-c:a", "libmp3lame", "-b:a", "320k"])
                    
            cmd.append(str(final_path))
            
            # Subprocess handles execution cleanly. Hide console on Windows.
            kwargs = {}
            if os.name == 'nt':
                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
                
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, **kwargs)
                        
        except Exception as e:
            print(f"Error during finalization: {e}")
        finally:
            # Let OS file handles release safely before deleting
            time.sleep(1.0)
            for temp_file in [self._temp_video, self._temp_mic]:
                if temp_file is not None and temp_file.exists():
                    try:
                        temp_file.unlink()
                    except Exception as e:
                        print(f"Could not delete temp file {temp_file.name}: {e}")


class RecorderApp(ctk.CTk):
    """Main Application GUI."""

    def __init__(self) -> None:
        super().__init__()

        self.title("Screen Recorder")
        self.geometry("500x580")
        self.resizable(False, False) 

        self.output_path_var = ctk.StringVar(value=str(DEFAULT_OUTPUT_DIR))
        self.format_var = ctk.StringVar(value="mp4")
        self.audio_source_var = ctk.StringVar(value="Microphone")
        self.theme_var = ctk.StringVar(value="Dark")
        
        self.recorder: ScreenRecorder = ScreenRecorder(Path(self.output_path_var.get()))
        
        # New robust timer variables
        self.elapsed_time: float = 0.0
        self.last_timer_time: float = 0.0

        self._setup_ui()
        self._apply_theme()

    def _setup_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure((0, 1, 2, 3, 4, 5, 6, 7, 8, 9), weight=1)

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

        self.label_format = ctk.CTkLabel(self.frame_options, text="Format:")
        self.label_format.grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.option_format = ctk.CTkOptionMenu(
            self.frame_options, values=list(FORMATS.keys()), variable=self.format_var
        )
        self.option_format.grid(row=0, column=1, padx=10, pady=5, sticky="e")

        self.label_audio = ctk.CTkLabel(self.frame_options, text="Audio Source:")
        self.label_audio.grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.option_audio = ctk.CTkOptionMenu(
            self.frame_options, values=["None", "Microphone"], variable=self.audio_source_var
        )
        self.option_audio.grid(row=1, column=1, padx=10, pady=5, sticky="e")

        self.label_theme = ctk.CTkLabel(self.frame_options, text="Theme:")
        self.label_theme.grid(row=2, column=0, padx=10, pady=5, sticky="w")
        self.option_theme = ctk.CTkOptionMenu(
            self.frame_options, values=["Light", "Dark"], variable=self.theme_var, command=self._apply_theme
        )
        self.option_theme.grid(row=2, column=1, padx=10, pady=5, sticky="e")

        # Status & Timer Labels
        self.label_status = ctk.CTkLabel(self, text="Ready to record", font=ctk.CTkFont(size=14))
        self.label_status.grid(row=4, column=0, padx=20, pady=5)

        self.label_timer = ctk.CTkLabel(self, text="00:00:00", font=ctk.CTkFont(size=20, weight="bold"))
        self.label_timer.grid(row=5, column=0, padx=20, pady=5)

        # Control Buttons
        self.btn_start = ctk.CTkButton(
            self, text="Start Recording", fg_color="green", hover_color="darkgreen", command=self._on_start
        )
        self.btn_start.grid(row=6, column=0, padx=20, pady=5)

        self.btn_pause = ctk.CTkButton(
            self, text="Pause Recording", fg_color="orange", hover_color="darkorange", 
            command=self._on_pause, state="disabled"
        )
        self.btn_pause.grid(row=7, column=0, padx=20, pady=5)

        self.btn_stop = ctk.CTkButton(
            self, text="Stop Recording", fg_color="red", hover_color="darkred", 
            command=self._on_stop, state="disabled"
        )
        self.btn_stop.grid(row=8, column=0, padx=20, pady=5)

    def _apply_theme(self, theme: str | None = None) -> None:
        ctk.set_appearance_mode(self.theme_var.get())

    def _on_choose_folder(self) -> None:
        from tkinter import filedialog
        try:
            folder_selected = filedialog.askdirectory(parent=self, title="Select Output Folder")
            if folder_selected:
                self.output_path_var.set(folder_selected)
                self.recorder.output_dir = Path(folder_selected)
                self.recorder.output_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"Error opening folder dialog: {e}")

    def _on_start(self) -> None:
        self.btn_start.configure(state="disabled")
        self.btn_browse.configure(state="disabled")
        self.option_format.configure(state="disabled")
        self.option_audio.configure(state="disabled")
        
        self.countdown = 3
        self._countdown_step()

    def _countdown_step(self) -> None:
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
            
            # Reset UI timer variables
            self.elapsed_time = 0.0
            self.last_timer_time = time.time()
            
            self.btn_stop.configure(state="normal")
            self.btn_pause.configure(state="normal", text="Pause Recording", fg_color="orange")
            self._update_timer()

    def _on_pause(self) -> None:
        if self.recorder.is_paused:
            self.recorder.resume()
            self.last_timer_time = time.time() # Reset to avoid jumping time
            self.btn_pause.configure(text="Pause Recording", fg_color="orange", hover_color="darkorange")
            self.label_status.configure(text="Recording...")
        else:
            self.recorder.pause()
            self.btn_pause.configure(text="Resume Recording", fg_color="#1E90FF", hover_color="#1874CD")
            self.label_status.configure(text="Paused")

    def _on_stop(self) -> None:
        self.label_status.configure(text="Saving fast... please wait.")
        self.btn_stop.configure(state="disabled")
        self.btn_pause.configure(state="disabled")
        self.update()
        
        threading.Thread(target=self._stop_recording_thread, daemon=True).start()

    def _stop_recording_thread(self) -> None:
        self.recorder.stop()
        self.after(0, self._on_stop_finished)

    def _on_stop_finished(self) -> None:
        self.btn_start.configure(state="normal")
        self.btn_browse.configure(state="normal")
        self.option_format.configure(state="normal")
        self.option_audio.configure(state="normal")
        self.label_status.configure(
            text=f"Saved: {self.recorder.current_filename}"
        )

    def _update_timer(self) -> None:
        if not self.recorder.is_recording:
            return
            
        now = time.time()
        delta = now - self.last_timer_time
        self.last_timer_time = now
        
        # Only increment actual elapsed seconds if not paused
        if not self.recorder.is_paused:
            self.elapsed_time += delta
            
        hours, rem = divmod(int(self.elapsed_time), 3600)
        minutes, seconds = divmod(rem, 60)
        self.label_timer.configure(text=f"{hours:02}:{minutes:02}:{seconds:02}")
        
        self.after(500, self._update_timer)


if __name__ == "__main__":
    app = RecorderApp()
    app.mainloop()