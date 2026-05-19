import unittest
from pathlib import Path
from Screen_recorder import ScreenRecorder
import time
import shutil

class TestScreenRecorder(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("test_recordings")
        self.recorder = ScreenRecorder(self.test_dir)

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_output_dir_creation(self):
        self.assertTrue(self.test_dir.exists())

    def test_recording_lifecycle_mp4(self):
        # Start recording in mp4
        self.recorder.start(video_format="mp4")
        self.assertTrue(self.recorder.is_recording)
        self.assertTrue(self.recorder.current_filename.endswith(".mp4"))
        
        time.sleep(1)
        self.recorder.stop()
        
        output_file = self.test_dir / self.recorder.current_filename
        self.assertTrue(output_file.exists())
        self.assertGreater(output_file.stat().st_size, 0)

    def test_recording_lifecycle_avi(self):
        # Start recording in avi
        self.recorder.start(video_format="avi")
        self.assertTrue(self.recorder.is_recording)
        self.assertTrue(self.recorder.current_filename.endswith(".avi"))
        
        time.sleep(1)
        self.recorder.stop()
        
        output_file = self.test_dir / self.recorder.current_filename
        self.assertTrue(output_file.exists())
        self.assertGreater(output_file.stat().st_size, 0)

    def test_custom_output_dir(self):
        custom_dir = Path("custom_recordings")
        self.recorder.output_dir = custom_dir
        self.recorder.output_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            self.recorder.start(video_format="mp4")
            time.sleep(1)
            self.recorder.stop()
            
            output_file = custom_dir / self.recorder.current_filename
            self.assertTrue(output_file.exists())
        finally:
            if custom_dir.exists():
                shutil.rmtree(custom_dir)


if __name__ == "__main__":
    unittest.main()
