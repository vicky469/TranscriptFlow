#!/usr/bin/env python3
"""
Complete workflow orchestrator for YouTube to Notion transcript processing.
Handles the entire pipeline from YouTube URL to Notion page creation.
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path
import webbrowser
import glob
import json
from notion_integration import NotionIntegration
from transcript_processor import process_file
from twitter_handler import TwitterThreadHandler

class TranscriptWorkflow:
    def __init__(self, base_dir=None):
        """Initialize the workflow with base directory."""
        if base_dir is None:
            import os
            current_file = os.path.abspath(__file__)
            repo_root = os.path.dirname(os.path.dirname(current_file))
            base_dir = repo_root
        
        self.base_dir = Path(base_dir)
        self.raw_dir = self.base_dir / "transcript" / "raw"
        self.failed_dir = self.base_dir / "transcript" / "failed"
        self.clean_dir = self.base_dir / "transcript" / "clean"
        
        # Ensure directories exist
        for directory in [self.raw_dir, self.failed_dir, self.clean_dir]:
            directory.mkdir(parents=True, exist_ok=True)
    
    def run_complete_workflow(self, url, open_notion=True):
        """
        Run the complete workflow from URL (YouTube or Twitter) to Notion page.
        
        Args:
            url (str): YouTube video URL or Twitter thread URL
            open_notion (bool): Whether to open the Notion page in browser
            
        Returns:
            dict: Results of each step
        """
        results = {
            'download': {'success': False},
            'process': {'success': False},
            'upload': {'success': False}
        }
        
        # Detect URL type and route accordingly
        # Check if it's a Twitter URL (simple check to avoid importing TwitterThreadHandler unnecessarily)
        is_twitter = 'twitter.com' in url or 'x.com' in url
        
        if is_twitter:
            print("🚀 Starting Twitter to Notion workflow...")
            print(f"🐦 URL: {url}")
            
            # Step 1: Download thread from Twitter (initialize handler only when needed)
            print("\n📥 Step 1: Downloading thread from Twitter...")
            twitter_handler = TwitterThreadHandler(self.base_dir)
            success, raw_file, content_info = twitter_handler.fetch_thread_content(url)
        else:
            print("🚀 Starting YouTube to Notion workflow...")
            print(f"📺 URL: {url}")
            
            # Step 1: Download transcript from YouTube using shell script
            print("\n📥 Step 1: Downloading transcript from YouTube...")
            success, raw_file, content_info = self._download_with_script(url)
        
        results['download'] = {
            'success': success,
            'file': raw_file,
            'content_info': content_info
        }
        
        if not success:
            print("❌ Failed to download transcript")
            return results
        
        print(f"✅ Downloaded: {os.path.basename(raw_file)}")
        
        # Step 2: Process transcript in-place
        print("\n🔄 Step 2: Processing transcript...")
        
        # Process the transcript directly from raw directory
        clean_file_path = self.clean_dir / f"{os.path.splitext(os.path.basename(raw_file))[0]}_clean.txt"
        success = process_file(str(raw_file), str(clean_file_path))
        
        results['process'] = {
            'success': success,
            'clean_file': str(clean_file_path) if success else None
        }
        
        if not success:
            print("❌ Failed to process transcript")
            # Move failed file to failed directory
            failed_file_path = self.failed_dir / os.path.basename(raw_file)
            try:
                shutil.move(raw_file, failed_file_path)
                print(f"📁 Moved failed file to: {failed_file_path}")
            except Exception as e:
                print(f"⚠️  Warning: Could not move failed file: {e}")
            return results
        
        print(f"✅ Processed transcript: {clean_file_path}")
        
        # Step 3: Upload to Notion
        print("\n☁️  Step 3: Uploading to Notion...")
        
        try:
            notion = NotionIntegration()
            
            # Tags will be managed manually in Notion
            
            success, page_url, page_id = notion.upload_transcript(
                str(clean_file_path),
                content_info=content_info
            )
            
            results['upload'] = {
                'success': success,
                'page_url': page_url,
                'page_id': page_id
            }
            
            if success:
                print(f"✅ Uploaded to Notion: {page_url}")
                
                # Clean up raw transcript file after successful upload
                try:
                    if os.path.exists(raw_file):
                        os.remove(raw_file)
                        print(f"🗑️  Cleaned up raw file: {os.path.basename(raw_file)}")
                        
                except Exception as e:
                    print(f"⚠️  Warning: Could not clean up raw file: {e}")
                
                # Open in browser if requested
                if open_notion and page_url:
                    print("🌐 Opening Notion page in browser...")
                    webbrowser.open(page_url)
            else:
                print("❌ Failed to upload to Notion")
                
        except Exception as e:
            print(f"❌ Error uploading to Notion: {e}")
            print("💡 Make sure you have set up your Notion integration and .env file")
            results['upload']['success'] = False
        
        # Summary
        print("\n📊 Workflow Summary:")
        print(f"   📥 Download: {'✅' if results['download']['success'] else '❌'}")
        print(f"   🔄 Process:  {'✅' if results['process']['success'] else '❌'}")
        print(f"   ☁️  Upload:   {'✅' if results['upload']['success'] else '❌'}")
        
        if all(step['success'] for step in results.values()):
            print("\n🎉 Workflow completed successfully!")
            if results['upload']['page_url']:
                print(f"🔗 Notion Page: {results['upload']['page_url']}")
        else:
            print("\n⚠️  Workflow completed with some failures")
        
        return results
    
    def _download_with_script(self, youtube_url):
        """Download transcript using the shell script."""
        try:
            script_path = self.base_dir / "scripts" / "download_transcript.sh"
            
            # Make script executable if not already
            os.chmod(script_path, 0o755)
            
            # Clear any existing transcript files to prevent reuse
            existing_vtt_files = glob.glob(str(self.raw_dir / "*.vtt"))
            existing_txt_files = glob.glob(str(self.raw_dir / "*whisper.txt"))
            
            for old_file in existing_vtt_files + existing_txt_files:
                os.remove(old_file)
                print(f"🗑️  Cleared old file: {os.path.basename(old_file)}")
            
            # Run the download script (don't capture output so we can see the method logs)
            result = subprocess.run(
                [str(script_path), youtube_url, str(self.raw_dir)],
                cwd=str(self.base_dir)
            )
            
            if result.returncode == 0:
                # Find the downloaded transcript file (VTT from subtitles or TXT from Whisper)
                vtt_files = glob.glob(str(self.raw_dir / "*.vtt"))
                txt_files = glob.glob(str(self.raw_dir / "*whisper.txt"))
                
                transcript_files = vtt_files + txt_files
                
                if transcript_files:
                    # Use the most recent file (should only be one now)
                    transcript_file = transcript_files[0]
                    
                    # Try to load metadata from JSON file
                    filename = os.path.basename(transcript_file)
                    base_name = os.path.splitext(filename)[0]
                    # Remove _whisper suffix if present
                    base_name = base_name.replace('_whisper', '')
                    
                    metadata_file = self.raw_dir / f"{base_name}.json"
                    
                    if os.path.exists(metadata_file):
                        try:
                            with open(metadata_file, 'r', encoding='utf-8') as f:
                                metadata = json.load(f)
                            
                            content_info = {
                                'title': metadata.get('title', base_name),
                                'duration': metadata.get('duration', 0),
                                'uploader': metadata.get('uploader', 'Unknown'),
                                'upload_date': metadata.get('upload_date', 'Unknown'),
                                'view_count': metadata.get('view_count', 0),
                                'description': metadata.get('description', ''),
                                'webpage_url': metadata.get('webpage_url', '')
                            }
                            print(f"📊 Loaded metadata: {content_info['uploader']} - {content_info['title']}")
                        except Exception as e:
                            print(f"⚠️  Could not load metadata: {e}")
                            content_info = {
                                'title': base_name,
                                'duration': 0,
                                'uploader': 'Unknown',
                                'upload_date': 'Unknown'
                            }
                    else:
                        # Fallback to basic info from filename
                        content_info = {
                            'title': base_name,
                            'duration': 0,
                            'uploader': 'Unknown',
                            'upload_date': 'Unknown'
                        }
                    
                    return True, transcript_file, content_info
                else:
                    print("❌ No transcript file found after trying all methods")
                    return False, None, None
            else:
                print(f"❌ Download script failed: {result.stderr}")
                return False, None, None
                
        except Exception as e:
            print(f"❌ Error running download script: {e}")
            return False, None, None
    
    def process_existing_transcript(self, transcript_file, open_notion=True):
        """
        Process an existing transcript file and upload to Notion.
        
        Args:
            transcript_file (str): Path to existing clean transcript file
            open_notion (bool): Whether to open the Notion page in browser
            
        Returns:
            dict: Upload results
        """
        print(f"📄 Processing existing transcript: {transcript_file}")
        
        try:
            notion = NotionIntegration()
            
            success, page_url, page_id = notion.upload_transcript(
                transcript_file
            )
            
            if success:
                print(f"✅ Uploaded to Notion: {page_url}")
                
                if open_notion and page_url:
                    print("🌐 Opening Notion page in browser...")
                    webbrowser.open(page_url)
                    
                return {
                    'success': True,
                    'page_url': page_url,
                    'page_id': page_id
                }
            else:
                print("❌ Failed to upload to Notion")
                return {'success': False}
                
        except Exception as e:
            print(f"❌ Error: {e}")
            return {'success': False}

def main():
    """Main function for command-line usage."""
    if len(sys.argv) < 2:
        print("🎯 Content to Notion Workflow")
        print("\nUsage:")
        print("  python workflow_orchestrator.py <url>")
        print("  python workflow_orchestrator.py --existing <transcript_file>")
        print("\nExamples:")
        print("  python workflow_orchestrator.py 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'")
        print("  python workflow_orchestrator.py 'https://x.com/username/status/1234567890'")
        print("  python workflow_orchestrator.py --existing transcript.txt")
        sys.exit(1)
    
    # Initialize workflow
    workflow = TranscriptWorkflow()
    
    # Check if processing existing file
    if sys.argv[1] == "--existing":
        if len(sys.argv) < 3:
            print("❌ Please provide a transcript file path")
            sys.exit(1)
        
        transcript_file = sys.argv[2]
        
        if not os.path.exists(transcript_file):
            print(f"❌ File not found: {transcript_file}")
            sys.exit(1)
        
        results = workflow.process_existing_transcript(transcript_file)
        
        if not results['success']:
            sys.exit(1)
    else:
        # Process URL (YouTube or Twitter)
        url = sys.argv[1]
        
        results = workflow.run_complete_workflow(url)
        
        # Exit with error code if any step failed
        if not all(step['success'] for step in results.values()):
            sys.exit(1)

if __name__ == "__main__":
    main()
