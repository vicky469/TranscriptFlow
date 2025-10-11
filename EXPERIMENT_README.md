// pip install -r requirements.txt

https://github.com/yt-dlp/yt-dlp/?tab=readme-ov-file#installation

## Templates:

// Basic template: Extract audio only (-x) and save with the video title as filename
`yt-dlp -x -o '/path/to/downloads/%(title)s.%(ext)s' 'youtube video link'`

// Template with channel name: Extract audio and include channel name in filename
`yt-dlp -x -o './audios/%(channel)s - %(title)s.%(ext)s' 'youtube video link'`

// Template with uploader and channel: Extract audio and include both uploader and channel in filename
`yt-dlp -x -o './audios/%(uploader)s - %(channel)s - %(title)s.%(ext)s' 'youtube video link'`

## Examples:

// Example 1: Extract audio only, saving with just the video title
yt-dlp -x -o './audios/%(title)s.%(ext)s' 'https://www.youtube.com/watch?v=xdZlAIQgNuM'

// Example 2: Extract audio and include the channel name in the filename
yt-dlp -x -o './audios/%(channel)s - %(title)s.%(ext)s' 'https://www.youtube.com/watch?v=RGRT78Sn8dE&ab_channel=ricarda'

// Example 3: Extract audio with time range (from 1:55 to 19:20) and include channel name in filename
yt-dlp -x --postprocessor-args "-ss 01:55 -to 19:20" -o './audios/%(channel)s - %(title)s.%(ext)s' 'https://www.youtube.com/watch?v=-8Whp_X6xoE&ab_channel=GhettoASMRReuploads'

// Example 4: Extract audio in MP3 format with time range (from 1:55 to 19:20) and include channel name in filename
yt-dlp -x --audio-format mp3 --postprocessor-args "-ss 01:55 -to 19:20" -o './audios/%(channel)s - %(title)s.%(ext)s' 'https://www.youtube.com/watch?v=-8Whp_X6xoE&ab_channel=GhettoASMRReuploads'

// Example 5: Extract audio in MP3 format and include channel name in filename
yt-dlp -x --audio-format mp3 -o './audios/%(channel)s - %(title)s.%(ext)s' 'https://www.youtube.com/watch?v=vNC1zr2XpKQ&ab_channel=VanessaASMR'

## Troubleshooting

### Fixing "Sign in to confirm you're not a bot" Error

// Method 1: Use browser cookies (recommended)
yt-dlp -x --audio-format mp3 --cookies-from-browser firefox -o './audios/%(channel)s - %(title)s.%(ext)s' 'https://www.youtube.com/watch?v=7hyoONj4nEY&ab_channel=JordanBPeterson'

### Fixing Requested format is not available. Use --list-formats for a list of available formats

// Method 1: Try with format 18 (combined audio/video) and extract audio
yt-dlp -f 18 -x --audio-format mp3 --extractor-args "youtube:player_client=android" --geo-bypass -o './audios/%(channel)s - %(title)s.%(ext)s' 'https://www.youtube.com/watch?v=7hyoONj4nEY'

## download the video

yt-dlp --cookies-from-browser chrome -o './videos/%(channel)s - %(title)s.%(ext)s' 'https://www.youtube.com/watch?v=yP96dkspUL8'
