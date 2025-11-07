# Video to Notion Transcript Processor

Automatically download video transcripts, clean them, and upload to Notion with rich metadata for note-taking.

## 🚀 Two Ways to Run

### Option 1: Web Interface (Recommended)

```bash
pip install -r requirements.txt
python -m streamlit run streamlit_app.py
```

Open `http://localhost:8501`, paste YouTube URL, and click "Process Video"

### Option 2: Command Line

```bash
pip install -r requirements.txt
python src/workflow_orchestrator.py "https://www.youtube.com/watch?v=VIDEO_ID"
```

## ⚙️ Setup (Required for Both Methods)

### 1. Create Notion Integration

1. Go to [https://www.notion.so/my-integrations](https://www.notion.so/my-integrations)
2. Click "New integration" → Copy the token
3. Create a database with: Title, Status, Author, Created, Duration, Views, Video URL
4. Share database with your integration → Copy database ID

### 2. Create Environment File

```bash
echo "NOTION_TOKEN=your_token_here" > .env
echo "NOTION_DATABASE_ID=your_database_id_here" >> .env
```

## 📁 File Structure

```text
audio classifier/
├── scripts/
│   └── download_transcript.sh      # YouTube transcript downloader
├── src/
│   ├── workflow_orchestrator.py    # Main workflow script
│   ├── notion_integration.py       # Notion API integration
│   ├── transcript_processor.py     # Transcript cleaner/formatter
│   └── whisper_transcriber.py      # Whisper audio transcription
├── streamlit_app.py                # Web interface application
├── transcript/
│   ├── raw/                        # Raw downloaded files (VTT/TXT)
│   ├── failed/                     # Files that failed processing
│   └── clean/                      # Cleaned, formatted transcripts
├── requirements.txt                # Python dependencies
└── .env                           # API keys and configuration
```

## 🎯 What It Does

1. **Download**: Extract transcripts and metadata from YouTube
2. **Process**: Clean and format with language-specific rules
3. **Upload**: Create organized Notion pages with rich metadata
4. **Cleanup**: Remove temporary files automatically

## 🤖 AI Transcription

For videos without subtitles, the system uses AI transcription with two backends:

- **faster-whisper** (Recommended): Optimized for Apple Silicon (M1/M2), 2-4x faster with lower memory usage
- **OpenAI Whisper**: Fallback option, works on all platforms but slower on Apple Silicon

The system automatically selects the best available backend. For optimal performance on M1/M2 Macs, ensure `faster-whisper` is installed.

## 🛠 Troubleshooting

- **"No transcript available"**: Video may not have subtitles or is private
- **"Notion token not found"**: Check your `.env` file has correct `NOTION_TOKEN`
- **"Permission denied"**: Ensure Notion integration has database access
- **MPS/GPU errors**: System automatically falls back to CPU or faster-whisper backend
