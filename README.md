# Screen Recorder

A modern, high-performance screen recording application built with Python. Designed for simplicity, speed, and reliability.

Whether you're creating tutorials, capturing gameplay, or recording meetings, this Screen Recorder provides a seamless experience with professional-grade results.

---

## Key Features

-   **Fast FFmpeg Encoding:** Leverages FFmpeg for ultra-fast video merging and high-quality compression.
-   **Seamless Pause/Resume:** Capture exactly what you need with precise control over your recording sessions.
-   **Audio Integration:** High-quality microphone recording synchronized perfectly with your screen.
-   **Modern UI:** A sleek, user-friendly interface built with `customtkinter`, featuring both **Dark** and **Light** themes.
-   **Precision Timer:** Real-time tracking of your recording duration.
-   **Customizable Output:** Choose your preferred save location and output format (MP4 or AVI).
-   **Smart Countdown:** A 3-second buffer to get you ready before recording begins.

---

## Tech Stack

-   **GUI:** [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter)
-   **Screen Capture:** [OpenCV](https://opencv.org/) & [Pillow](https://python-pillow.org/)
-   **Audio:** [sounddevice](https://python-sounddevice.readthedocs.io/)
-   **Encoding:** [FFmpeg](https://ffmpeg.org/) (via `imageio-ffmpeg`)
-   **Architecture:** Multi-threaded for a responsive UI and lag-free recording.

---

## Getting Started

### Prerequisites

Ensure you have Python 3.12+ installed.

### Installation

1.  **Clone the repository:**
2.  **Create and activate a virtual environment:**
    ```bash
    python -m venv .venv
    # Windows
    .venv\Scripts\activate
    # Linux/macOS
    source .venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

> [!NOTE] 
> On Linux, you might need to install `portaudio` for `sounddevice` to work.*

---

## Usage

1.  **Launch the application:**
    ```bash
    python Screen_recorder.py
    ```
2.  **Configure your session:**
    -   Select the **Output Folder**.
    -   Choose your preferred **Format** (MP4 or AVI).
    -   Select **Audio Source** (Microphone or None).
3.  **Record:**
    -   Click **Start Recording** (Wait for the 3-second countdown).
    -   Use **Pause/Resume** as needed.
    -   Click **Stop Recording** to finalize and save your video.

---

## Testing

The project includes a suite of unit tests to ensure stability across recording formats and lifecycles.

To run the tests:
```bash
pytest test_screen_recorder.py
```

---

## Contributing

Contributions are welcome! Whether it's a bug fix, a new feature, or an improvement to the documentation, feel free to open an issue or submit a pull request.

---

## License

This project is open-source and available under the [MIT License](LICENSE).

---

