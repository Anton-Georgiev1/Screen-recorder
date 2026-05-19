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

    def test_recording_lifecycle(self):
        # Start recording
        self.recorder.start()
        self.assertTrue(self.recorder.is_recording)
        self.assertIsNotNone(self.recorder.current_filename)
        
        # Record for 2 seconds
        time.sleep(2)
        
        # Stop recording
        self.recorder.stop()
        self.assertFalse(self.recorder.is_recording)
        
        # Check if file exists
        output_file = self.test_dir / self.recorder.current_filename
        self.assertTrue(output_file.exists())
        self.assertGreater(output_file.stat().st_size, 0)

if __name__ == "__main__":
    unittest.main()
