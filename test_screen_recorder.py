import time
from pathlib import Path
import pytest
from Screen_recorder import ScreenRecorder

@pytest.fixture
def recorder(tmp_path: Path) -> ScreenRecorder:
    """Fixture to provide a ScreenRecorder instance with a temporary output directory."""
    return ScreenRecorder(tmp_path)

def test_output_dir_creation(tmp_path: Path):
    """Verify that the output directory is created on initialization."""
    recorder = ScreenRecorder(tmp_path)
    assert tmp_path.exists()

def test_recording_lifecycle_mp4(recorder: ScreenRecorder, tmp_path: Path):
    """Test the full lifecycle of an MP4 recording."""
    recorder.start(video_format="mp4")
    assert recorder.is_recording
    assert recorder.current_filename.endswith(".mp4")
    
    time.sleep(1)
    recorder.stop()
    
    assert not recorder.is_recording
    output_file = tmp_path / recorder.current_filename
    assert output_file.exists()
    assert output_file.stat().st_size > 0

def test_recording_lifecycle_avi(recorder: ScreenRecorder, tmp_path: Path):
    """Test the full lifecycle of an AVI recording."""
    recorder.start(video_format="avi")
    assert recorder.is_recording
    assert recorder.current_filename.endswith(".avi")
    
    time.sleep(1)
    recorder.stop()
    
    assert not recorder.is_recording
    output_file = tmp_path / recorder.current_filename
    assert output_file.exists()
    assert output_file.stat().st_size > 0

def test_pause_resume(recorder: ScreenRecorder, tmp_path: Path):
    """Test the pause and resume functionality during recording."""
    recorder.start(video_format="mp4")
    assert recorder.is_recording
    assert not recorder.is_paused
    
    recorder.pause()
    assert recorder.is_paused
    
    time.sleep(0.5)
    
    recorder.resume()
    assert not recorder.is_paused
    
    time.sleep(0.5)
    recorder.stop()
    
    output_file = tmp_path / recorder.current_filename
    assert output_file.exists()
    assert output_file.stat().st_size > 0

def test_custom_output_dir(tmp_path: Path):
    """Test changing the output directory after initialization."""
    recorder = ScreenRecorder(tmp_path)
    custom_dir = tmp_path / "custom_subdir"
    recorder.output_dir = custom_dir
    recorder.output_dir.mkdir(parents=True, exist_ok=True)
    
    recorder.start(video_format="mp4")
    time.sleep(0.5)
    recorder.stop()
    
    output_file = custom_dir / recorder.current_filename
    assert output_file.exists()
