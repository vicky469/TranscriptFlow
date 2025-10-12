#!/usr/bin/env python3
"""
Whisper-based transcription for videos without subtitles.
Supports Chinese and other languages.
"""

import os
import subprocess
import platform
import time
from pathlib import Path

class WhisperTranscriber:
    def __init__(self, model_size="base"):
        """Initialize Whisper model - faster-whisper for M1/M2, fallback to CPU whisper."""
        self.use_faster_whisper = False
        
        # Check if running on Apple Silicon
        is_apple_silicon = platform.machine() == "arm64" and platform.system() == "Darwin"
        
        if is_apple_silicon:
            try:
                from faster_whisper import WhisperModel
                # Try GPU first, fallback to CPU if needed
                try:
                    self.model = WhisperModel(model_size, device="auto", compute_type="auto")
                    print("🚀 Using faster-whisper with GPU acceleration (Apple Silicon)")
                except Exception:
                    self.model = WhisperModel(model_size, device="cpu", compute_type="int8")
                    print("🚀 Using faster-whisper on CPU (Apple Silicon optimized)")
                self.use_faster_whisper = True
            except Exception:
                import whisper
                self.model = whisper.load_model(model_size)
                print("⚠️ Using OpenAI Whisper on CPU")
        else:
            import whisper
            self.model = whisper.load_model(model_size)
            print("⚠️ Using OpenAI Whisper on CPU")
    
    def transcribe_youtube_video(self, youtube_url, output_dir, language=None):
        """
        Download audio from YouTube and transcribe using Whisper.
        
        Args:
            youtube_url (str): YouTube video URL
            output_dir (str): Directory to save transcript
            language (str): Language code (e.g., 'zh', 'en') or None for auto-detect
            
        Returns:
            tuple: (success, transcript_file_path, transcript_text)
        """
        try:
            # Create temp directory for audio
            temp_dir = Path(output_dir) / "temp"
            temp_dir.mkdir(exist_ok=True)
            
            # Download audio using yt-dlp with progress
            print("📥 Downloading audio from YouTube...")
            download_start = time.time()
            
            # Try download with verbose mode if first attempt fails
            for attempt in range(2):
                cmd = [
                    "yt-dlp",
                    "--extract-audio",
                    "--audio-format", "wav",
                    "--output", str(temp_dir / "audio.%(ext)s"),
                    "--progress",  # Show progress
                    "--newline",   # Print progress on new lines for better parsing
                    # Add headers to avoid 403 errors
                    "--user-agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                    "--referer", "https://www.youtube.com/",
                    # Retry settings
                    "--retries", "3",
                    "--fragment-retries", "3",
                    "--skip-unavailable-fragments",  # Skip fragments that fail
                ]
                
                # Add verbose flag on second attempt for debugging
                if attempt == 1:
                    print("🔍 Retrying with verbose output for diagnostics...")
                    cmd.extend(["-v", "--update"])  # Verbose and update check
                
                cmd.append(youtube_url)
                
                # Run with real-time output instead of capturing
                try:
                    result = subprocess.run(cmd, text=True, timeout=180)  # 3 minute timeout
                    download_time = time.time() - download_start
                    
                    if result.returncode == 0:
                        print(f"✅ Download completed in {download_time:.1f} seconds")
                        break
                    elif attempt == 0:
                        print(f"⚠️  First attempt failed, trying again with diagnostics...")
                        continue
                    else:
                        print(f"⚠️  Download had issues but checking for partial audio...")
                        
                except subprocess.TimeoutExpired:
                    if attempt == 0:
                        print("⚠️  First attempt timed out, trying once more...")
                        continue
                    else:
                        print("❌ Download timed out after 3 minutes on retry")
                        return False, None, "Download timed out"
                except KeyboardInterrupt:
                    print("\n⚠️  Download cancelled by user")
                    return False, None, "Download cancelled"
            
            # Find the downloaded audio file
            audio_files = list(temp_dir.glob("audio.*"))
            if not audio_files:
                return False, None, "No audio file found after download"
            
            actual_audio_file = audio_files[0]
            
            # Transcribe using appropriate Whisper backend
            print(f"🎤 Transcribing audio (language: {language or 'auto-detect'})...")
            transcription_start = time.time()
            
            if self.use_faster_whisper:
                print("⏳ Processing with faster-whisper...")
                segments, info = self.model.transcribe(
                    str(actual_audio_file), 
                    language=language,
                    beam_size=1,  # Faster but less accurate
                    best_of=1     # Single pass for speed
                )
                transcript_text = " ".join([segment.text for segment in segments])
                transcription_time = time.time() - transcription_start
                print(f"✅ faster-whisper completed in {transcription_time:.1f} seconds")
            else:
                print("⏳ Processing with OpenAI Whisper...")
                result = self.model.transcribe(str(actual_audio_file), language=language, fp16=False)
                transcript_text = result["text"]
                transcription_time = time.time() - transcription_start
                print(f"✅ OpenAI Whisper completed in {transcription_time:.1f} seconds")
            
            # Get video title for filename
            title_cmd = ["yt-dlp", "--print", "title", youtube_url]
            title_result = subprocess.run(title_cmd, capture_output=True, text=True)
            
            if title_result.returncode == 0:
                title = title_result.stdout.strip()
                # Clean title for filename
                title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
                transcript_file = Path(output_dir) / f"{title}_whisper.txt"
            else:
                video_id = youtube_url.split("v=")[1].split("&")[0] if "v=" in youtube_url else "unknown"
                transcript_file = Path(output_dir) / f"{video_id}_whisper_transcript.txt"
            
            with open(transcript_file, 'w', encoding='utf-8') as f:
                f.write(transcript_text)
            
            # Clean up temp directory
            import shutil
            shutil.rmtree(temp_dir)
            
            return True, str(transcript_file), transcript_text
            
        except Exception as e:
            return False, None, f"Transcription error: {e}"

def main():
    """Command line usage."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python whisper_transcriber.py <youtube_url> [language_code]")
        print("Example: python whisper_transcriber.py 'https://youtube.com/watch?v=...' zh")
        sys.exit(1)
    
    url = sys.argv[1]
    language = sys.argv[2] if len(sys.argv) > 2 else None
    
    transcriber = WhisperTranscriber()
    # Use absolute path
    import os
    current_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.dirname(current_dir)
    output_dir = os.path.join(base_dir, "transcript", "raw")
    
    success, file_path, text = transcriber.transcribe_youtube_video(url, output_dir, language)
    
    if success:
        print(f"✅ Transcription completed: {file_path}")
        print(f"📝 Preview: {text[:200]}...")
    else:
        print(f"❌ Transcription failed: {text}")

if __name__ == "__main__":
    main()
