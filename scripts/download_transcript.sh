#!/bin/bash

#===============================================================================
# YouTube Transcript Downloader
#===============================================================================
# Description: Downloads YouTube video transcripts using multiple fallback methods
# Usage: ./download_transcript.sh <youtube_url>
#===============================================================================

set -euo pipefail  # Exit on error, undefined vars, pipe failures

#===============================================================================
# CONFIGURATION
#===============================================================================

# Directory setup
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly BASE_DIR="$(dirname "$SCRIPT_DIR")"
readonly TRANSCRIPT_DIR="$BASE_DIR/transcript/raw"


#===============================================================================
# UTILITY FUNCTIONS
#===============================================================================

# Display usage information
show_usage() {
    echo "Usage: $0 <youtube_url>"
    echo "Example: $0 'https://www.youtube.com/watch?v=VIDEO_ID'"
}

# Log messages with emoji indicators
log_info() { echo "ℹ️  $1"; }
log_success() { echo "✅ $1"; }
log_warning() { echo "⚠️  $1"; }
log_error() { echo "❌ $1"; }
log_progress() { echo "🔄 $1"; }

# Save metadata JSON file for transcript
save_metadata() {
    local file_pattern="$1"
    local file_extension="$2"
    
    local transcript_file
    transcript_file=$(ls "$TRANSCRIPT_DIR"/$file_pattern 2>/dev/null | head -1 || true)
    
    if [[ -n "$transcript_file" ]]; then
        local base_name
        base_name=$(basename "$transcript_file" "$file_extension")
        echo "$METADATA" > "$TRANSCRIPT_DIR/${base_name}.json"
        log_info "Saved metadata: ${base_name}.json"
    fi
}

#===============================================================================
# METADATA EXTRACTION
#===============================================================================

# Extract and validate video metadata
extract_metadata() {
    local youtube_url="$1"
    
    log_progress "Extracting video metadata..."
    
    # Get full metadata first
    local full_metadata
    full_metadata=$(yt-dlp --user-agent "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36" --referer "https://www.youtube.com/" --dump-json --no-warnings "$youtube_url" 2>/dev/null || true)
    
    if [[ -z "$full_metadata" ]]; then
        log_error "Failed to fetch video metadata"
        exit 1
    fi
    
    # Extract only essential metadata using jq
    local initial_metadata
    initial_metadata=$(echo "$full_metadata" | jq '{
        id: .id,
        title: .title,
        uploader: .uploader,
        upload_date: .upload_date,
        duration: .duration,
        view_count: .view_count,
        like_count: .like_count,
        description: .description,
        tags: .tags,
        categories: .categories,
        language: .language,
        webpage_url: .webpage_url,
        thumbnail: .thumbnail
    }' 2>/dev/null || echo "$full_metadata")
    
    # Detect language if not provided
    local detected_language
    local current_language
    current_language=$(echo "$initial_metadata" | jq -r '.language // empty' 2>/dev/null)
    
    if [[ -z "$current_language" || "$current_language" == "null" ]]; then
        log_progress "Language not detected, analyzing text content..."
        
        # Get title for analysis
        local title
        title=$(echo "$initial_metadata" | jq -r '.title // ""' 2>/dev/null)
        
        # Debug logging
        log_info "DEBUG - Title: '$title'"
        log_info "DEBUG - Title length: ${#title}"
        
        # Count Chinese characters vs English words in title using Python
        local chinese_words english_words total_units ratio
        read chinese_words english_words total_units ratio <<< $(python3 -c "
import re
text = '''$title'''
# Chinese words including Traditional Chinese
chinese_words = len(re.findall(r'[\u4e00-\u9fff]', text))
# English words: sequences of English letters
english_words = len(re.findall(r'[a-zA-Z]+', text))
total_units = chinese_words + english_words
ratio = chinese_words / total_units if total_units > 0 else 0
print(chinese_words, english_words, total_units, f'{ratio:.2f}')
" 2>/dev/null || echo "0 0 1 0.00")
        
        log_info "DEBUG - Chinese words found: $chinese_words"
        log_info "DEBUG - English words found: $english_words"
        log_info "DEBUG - Total units: $total_units"
        log_info "DEBUG - Ratio: $ratio"
        
        # If more than 40% Chinese words, consider it Chinese
        if [[ $total_units -gt 0 && $chinese_words -gt 0 ]]; then
            if (( $(echo "$ratio > 0.4" | bc -l 2>/dev/null || echo "0") )); then
                detected_language="zh"
                log_info "Detected Chinese (${chinese_words}/${total_units} = ${ratio})"
            else
                detected_language="en"
                log_info "Detected English (${chinese_words}/${total_units} = ${ratio})"
            fi
        else
            detected_language="en"
            log_info "Defaulting to English (chinese_words=$chinese_words, total_units=$total_units)"
        fi
        
        # Update metadata with detected language
        METADATA=$(echo "$initial_metadata" | jq --arg lang "$detected_language" '.language = $lang' 2>/dev/null || echo "$initial_metadata")
    else
        METADATA="$initial_metadata"
        log_info "Using original language: $current_language"
    fi
    
    # Export for Python consumption
    export YOUTUBE_METADATA="$METADATA"
    
    log_success "Metadata extracted successfully"
}


#===============================================================================
# DOWNLOAD METHODS
#===============================================================================

# Method 1: Download using YouTube's built-in subtitles
download_standard_subtitles() {
    log_progress "Method 1: Trying standard download..."
    
    yt-dlp --user-agent "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36" --referer "https://www.youtube.com/" \
        --write-auto-subs --sub-langs "en,zh,zh-CN,zh-TW" --sub-format "vtt" --skip-download \
        --output "$TRANSCRIPT_DIR/%(title)s.%(ext)s" "$YOUTUBE_URL" 2>/dev/null || true
    
    if ls "$TRANSCRIPT_DIR"/*.vtt 1>/dev/null 2>&1; then
        save_metadata "*.vtt" ".vtt"
        log_success "Downloaded transcript (Method 1: Standard)"
        return 0
    else
        log_warning "Method 1 failed - no subtitles available"
        return 1
    fi
}

# Method 2: Fallback to Whisper AI transcription
download_whisper_transcription() {
    log_progress "Method 2: No subtitles found, trying Whisper transcription..."
    
    cd "$BASE_DIR"
    
    if python src/whisper_transcriber.py "$YOUTUBE_URL"; then
        save_metadata "*whisper.txt" ".txt"
        log_success "Downloaded transcript (Method 2: Whisper transcription)"
        return 0
    else
        log_error "Whisper transcription failed"
        return 1
    fi
}

#===============================================================================
# MAIN EXECUTION
#===============================================================================

main() {
    # Validate arguments
    if [[ $# -lt 1 ]]; then
        show_usage
        exit 1
    fi
    
    readonly YOUTUBE_URL="$1"
    
    # Setup environment
    mkdir -p "$TRANSCRIPT_DIR"
    log_info "Downloading transcript from: $YOUTUBE_URL"
    
    # Extract metadata
    extract_metadata "$YOUTUBE_URL"
    
    # Try download methods in order of preference
    if download_standard_subtitles; then
        exit 0
    elif download_whisper_transcription; then
        exit 0
    else
        log_error "No transcript available (all methods failed)"
        exit 1
    fi
}

# Execute main function with all arguments
main "$@"
