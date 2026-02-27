#!/usr/bin/env python3
"""
Notion API integration for uploading cleaned transcripts to Notion workspace.
Creates pages with transcript content and metadata for note-taking.
"""

import os
import sys
import time
from datetime import datetime
from notion_client import Client
from dotenv import load_dotenv
import requests

# Load environment variables
load_dotenv()

class NotionIntegration:
    def __init__(self, token=None, database_id=None):
        """Initialize Notion client with token and database ID."""
        self.token = token or os.getenv('NOTION_TOKEN')
        self.database_id = database_id or os.getenv('NOTION_DATABASE_ID')
        
        if not self.token:
            raise ValueError("Notion token not found. Please set NOTION_TOKEN in .env file")
        
        if not self.database_id:
            error_msg = "Notion database ID is required. Please set NOTION_DATABASE_ID in .env file"
            print(f"ERROR: {error_msg}")
            raise ValueError(error_msg)
        
        self.client = Client(auth=self.token)
    
    def _add_content_metadata(self, properties, content_info):
        """Add content metadata to Notion page properties."""
        if not content_info:
            return properties
        
        # Use 'uploader' field for Author (channel name)
        if content_info.get('uploader'):
            properties["Author"] = {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": content_info['uploader']
                        }
                    }
                ]
            }
        
        # Handle creation date (date only, no time)
        # Format as rich_text for compatibility with existing database
        if content_info.get('created_time'):
            try:
                dt = datetime.fromisoformat(content_info['created_time'])
                formatted_date = dt.strftime('%Y-%m-%d')  # Date only
            except:
                formatted_date = content_info['created_time'].split('T')[0]  # Fallback: take date part
            
            properties["Created"] = {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": formatted_date
                        }
                    }
                ]
            }
        elif content_info.get('upload_date') and content_info['upload_date'] != 'Unknown':
            # YouTube video with YYYYMMDD format
            upload_date = content_info['upload_date']
            # Format YYYYMMDD to YYYY-MM-DD if it's in that format
            if len(upload_date) == 8 and upload_date.isdigit():
                formatted_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}"
            else:
                formatted_date = str(upload_date)
            
            properties["Created"] = {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": formatted_date
                        }
                    }
                ]
            }
        
        # Convert duration from seconds to minutes for display
        if content_info.get('duration') and content_info['duration'] > 0:
            duration_min = str(int(content_info['duration']) // 60)
            properties["Duration"] = {
                "phone_number": duration_min
            }
        
        # Add view count if available
        if content_info.get('view_count') and content_info['view_count'] > 0:
            view_count = f"{content_info['view_count']:,}"  # Format with commas
            properties["Views"] = {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": view_count
                        }
                    }
                ]
            }
        
        # Add content URL if available
        content_url = content_info.get('webpage_url') or content_info.get('url')
        if content_url:
            properties["Content URL"] = {
                "url": content_url
            }
        
        properties["Source"] = {
            "select": {
                "name": "YouTube"
            }
        }
        
        return properties
        
    def _retry_api_call(self, func, *args, **kwargs):
        """
        Retry API calls with exponential backoff for timeout/connection errors.
        
        Args:
            func: Function to call
            *args, **kwargs: Arguments to pass to the function
            
        Returns:
            Result of the function call
        """
        max_retries = 3
        base_delay = 1  # Start with 1 second delay
        
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except (requests.exceptions.Timeout, 
                    requests.exceptions.ConnectionError,
                    requests.exceptions.ReadTimeout,
                    Exception) as e:
                
                # Check if it's a timeout-related error
                error_msg = str(e).lower()
                is_timeout = any(keyword in error_msg for keyword in 
                               ['timeout', 'timed out', 'connection', 'read timeout'])
                
                if attempt < max_retries - 1 and is_timeout:
                    delay = base_delay * (2 ** attempt)  # Exponential backoff
                    print(f"⚠️  API call failed (attempt {attempt + 1}/{max_retries}): {e}")
                    print(f"🔄 Retrying in {delay} seconds...")
                    time.sleep(delay)
                else:
                    # Last attempt or non-timeout error, re-raise
                    raise e
    
    def create_page_in_database(self, title, content, content_info=None):
        """
        Create a new page in the specified Notion database.
        
        Args:
            title (str): Page title
            content (str): Transcript content
            content_info (dict): Content metadata (title, uploader, etc.)
            
        Returns:
            tuple: (success, page_url, page_id)
        """
        try:
            # Prepare properties for the database entry
            properties = {
                "Title": {
                    "title": [
                        {
                            "text": {
                                "content": title
                            }
                        }
                    ]
                }
            }
            
            # Add content metadata if available
            properties = self._add_content_metadata(properties, content_info)
            
            # Create the page first without content (to avoid 100 block limit)
            # Create in database with retry
            response = self._retry_api_call(
                self.client.pages.create,
                parent={"database_id": self.database_id},
                properties=properties
            )
            
            page_id = response["id"]
            page_url = response["url"]
            
            # Now add content in batches (Notion limit is 100 blocks per request)
            content_blocks = self._create_content_blocks(content, content_info)
            batch_size = 90  # Use 90 to be safe
            
            for i in range(0, len(content_blocks), batch_size):
                batch = content_blocks[i:i + batch_size]
                self._retry_api_call(
                    self.client.blocks.children.append,
                    block_id=page_id,
                    children=batch
                )
            
            print(f"✅ Created Notion page: {title}")
            print(f"🔗 URL: {page_url}")
            
            return True, page_url, page_id
            
        except Exception as e:
            print(f"❌ Error creating Notion page: {e}")
            return False, None, None
    
    def _create_content_blocks(self, content, content_info=None):
        """Convert transcript content into Notion blocks."""
        blocks = []

        # Use default transcript layout
        # Add content heading
        blocks.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": "📝 Content"
                        }
                    }
                ]
            }
        })
        
        # Use the same chunking as transcript_processor - content is already properly formatted
        # Split by double newlines to preserve the paragraph chunks
        chunks = content.split('\n\n')
        
        for chunk in chunks:
            if chunk.strip():
                # Remove internal line breaks within each chunk to create proper paragraphs
                clean_chunk = chunk.replace('\n', ' ').strip()
                blocks.append(self._create_paragraph_block(clean_chunk))
        
        # Add a divider and notes section
        blocks.extend([
            {
                "object": "block",
                "type": "divider",
                "divider": {}
            },
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": "📝 Add your notes here..."
                            }
                        }
                    ]
                }
            }
        ])
        
        return blocks
    
    def _create_paragraph_block(self, text):
        """Create a paragraph block for Notion."""
        return {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": text
                        }
                    }
                ]
            }
        }
    
    def upload_transcript(self, transcript_file, content_info=None):
        """
        Upload a cleaned transcript file to Notion.
        
        Args:
            transcript_file (str): Path to the transcript file
            content_info (dict): Content metadata to add to the page
            
        Returns:
            tuple: (success, page_url, page_id)
        """
        try:
            # Read the transcript content
            with open(transcript_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Generate title from filename or video info
            if content_info and content_info.get('title'):
                title = f"📺 {content_info['title']}"
            else:
                filename = os.path.basename(transcript_file)
                title = f"📺 {os.path.splitext(filename)[0].replace('_clean', '')}"
            
            return self.create_page_in_database(title, content, content_info)
            
        except Exception as e:
            print(f"❌ Error uploading transcript: {e}")
            return False, None, None

def main():
    """Main function for command-line usage."""
    if len(sys.argv) < 2:
        print("Usage: python notion_integration.py <transcript_file> [tags...]")
        print("Example: python notion_integration.py transcript.txt education blockchain")
        sys.exit(1)
    
    transcript_file = sys.argv[1]
    tags = sys.argv[2:] if len(sys.argv) > 2 else None
    
    # Initialize Notion integration
    try:
        notion = NotionIntegration()
        success, page_url, page_id = notion.upload_transcript(transcript_file, tags=tags)
        
        if success:
            print(f"🎉 Successfully uploaded to Notion!")
            print(f"🔗 Page URL: {page_url}")
        else:
            print("❌ Failed to upload to Notion")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\n📝 Setup Instructions:")
        print("1. Create a Notion integration at https://www.notion.so/my-integrations")
        print("2. Copy your integration token")
        print("3. Create a .env file with: NOTION_TOKEN=your_token_here")
        print("4. Optionally add: NOTION_DATABASE_ID=your_database_id")
        sys.exit(1)

if __name__ == "__main__":
    main()
