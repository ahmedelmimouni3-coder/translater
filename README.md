# Translator


A simple desktop text translation program, built in Python using PyQt6.


**Developer:** Ahmed Elmimouni
**Current version:** 2.2.1


## Features
- Translate handwritten text or imported from a `.txt` file, **using Google Gemini AI models only** (no traditional translation libraries)
- Choose the Gemini model and enter your API key in Settings
- Select target language from expandable list (`data/languages.json`)
- Spelling correction with Gemini
- **Text to speech (Ctrl+4):** converts the translation to speech with Gemini TTS models.
  Choose the speech model, the voice (press Space on the voices list to hear a sample) and an optional speaking style, then press *Convert to speech*. Play, Stop and Save buttons appear when it finishes.
- Convert audio/video files of **any size and almost any extension** (mp3, m4a, wav, ogg, opus, flac, wma, amr, mp4, mkv, ... or any file via *All files*) to text. ffmpeg decodes the file and splits it at silences into parts of at most 30 seconds, and every part is converted by `transcribe_audio_file` in `functions/speech_to_text.py` (SpeechRecognition with the free Google service; you choose the language spoken in the file, silent parts are skipped and low-confidence guesses are dropped instead of being inserted as invented text). Progress is announced; press Ctrl+2 again to cancel and keep the text so far. Without ffmpeg only WAV (split in pieces), AIFF and FLAC files work.
- Convert text to an image (Arabic is shaped with arabic_reshaper and reordered by a small built-in routine; python-bidi is no longer used)
- Save the translation result as a text file
- Automatic update system that checks for a newer version when the program is opened (connected to the Internet)

## Requirements
See `requirements.txt` (PyQt6, requests, pyperclip, accessible_output3, imageio-ffmpeg, SpeechRecognition, Pillow, arabic_reshaper). `imageio-ffmpeg` provides the bundled ffmpeg used to decode and split audio.

## Build
Double-click `build.bat`. It does not create a virtual environment and does not install anything: it uses the Python, PyInstaller and libraries already installed on your PC (`requirements.txt` lists the libraries the program uses). It builds with `Translator.spec`, which bundles the helper files of the `functions` and `update` folders, keeps only the PyQt6 modules the program uses (QtCore, QtGui, QtWidgets) and removes every other Qt module, plugin, translation file and software-OpenGL DLL, and bundles ffmpeg and the screen-reader DLLs. Then it copies the `data` folder (UI languages, program info, `languages.json`, icons) next to the executable and checks the result.

The output is `dist\Translator\Translator.exe`; open `setup.iss` with Inno Setup to create the installer.

## Structure
- `translater.py` - main window
- `tts_dialog.py` - text-to-speech window
- `user_guide.py` - "How to use" window
- `functions/gemini_ai.py` - all Gemini calls (translation, correction, TTS) over the REST API
- `functions/audio_player.py` - WAV playback (winsound)
- `Translator.spec` / `build.bat` - lean PyInstaller build
- `functions/speech_to_text.py` - `transcribe_audio_file`: converts one audio file to text
- `functions/audio_transcribe.py` - ffmpeg decoding, silence-based splitting and the loop that feeds every part to `transcribe_audio_file`

## Troubleshooting
If a transcription fails, the message shows the real reason and the details are saved in `%APPDATA%\Translator\translator_errors.log`.
