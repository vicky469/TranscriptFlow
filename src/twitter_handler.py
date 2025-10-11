#!/usr/bin/env python3
"""
Twitter/X thread handler using Thread Reader App.
Extracts thread content and prepares it for Notion upload.
"""

import re
import requests
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup
import json


class TwitterThreadHandler:
    """Handler for extracting Twitter/X threads using Thread Reader App."""
    
    def __init__(self, base_dir=None):
        """Initialize the Twitter handler."""
        if base_dir is None:
            import os
            current_file = os.path.abspath(__file__)
            repo_root = os.path.dirname(os.path.dirname(current_file))
            base_dir = repo_root
        
        self.base_dir = Path(base_dir)
        self.raw_dir = self.base_dir / "transcript" / "raw"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
    
    def is_twitter_url(self, url):
        """
        Check if URL is a Twitter/X URL.
        
        Args:
            url (str): URL to check
            
        Returns:
            bool: True if Twitter/X URL
        """
        if not url:
            return False
        
        # Match twitter.com or x.com URLs
        twitter_patterns = [
            r'https?://(www\.)?(twitter\.com|x\.com)/.+/status/\d+',
        ]
        
        return any(re.match(pattern, url) for pattern in twitter_patterns)
    
    def extract_tweet_id(self, url):
        """
        Extract tweet ID from Twitter/X URL.
        
        Args:
            url (str): Twitter/X URL
            
        Returns:
            str: Tweet ID or None
        """
        match = re.search(r'/status/(\d+)', url)
        if match:
            return match.group(1)
        return None
    
    def extract_username(self, url):
        """
        Extract username from Twitter/X URL.
        
        Args:
            url (str): Twitter/X URL
            
        Returns:
            str: Username or None
        """
        match = re.search(r'/([\w]+)/status/', url)
        if match:
            return match.group(1)
        return None
    
    def infer_title_from_content(self, thread_content, username):
        """
        Infer a meaningful title from the thread content.
        
        Args:
            thread_content (str): Full thread text
            username (str): Twitter username
            
        Returns:
            str: Inferred title
        """
        # Get first tweet (usually contains the main topic)
        first_tweet = thread_content.split('\n\n')[0] if thread_content else ""
        
        # Clean up the text
        first_tweet = first_tweet.strip()
        
        # Remove URLs from the first tweet
        first_tweet = re.sub(r'https?://\S+', '', first_tweet)
        
        # Remove "(thread)" or similar markers
        first_tweet = re.sub(r'\(thread\)|\[thread\]', '', first_tweet, flags=re.IGNORECASE)
        
        # Truncate to reasonable length (max 100 chars)
        if len(first_tweet) > 100:
            # Try to cut at sentence boundary
            sentences = re.split(r'[.!?]\s+', first_tweet)
            if sentences and len(sentences[0]) <= 100:
                title = sentences[0]
            else:
                # Cut at word boundary
                title = first_tweet[:97] + "..."
        else:
            title = first_tweet
        
        # If title is too short or empty, use a generic one
        if len(title.strip()) < 20:
            title = f"Thread by @{username}"
        
        return title.strip()
    
    def fetch_thread_content(self, twitter_url):
        """
        Fetch thread content using Thread Reader App CLI tool.
        
        Args:
            twitter_url (str): Twitter/X thread URL
            
        Returns:
            tuple: (success, content_file, thread_info)
        """
        try:
            print(f"🐦 Fetching Twitter thread from: {twitter_url}")
            
            tweet_id = self.extract_tweet_id(twitter_url)
            username = self.extract_username(twitter_url)
            
            if not tweet_id or not username:
                print("❌ Could not extract tweet ID or username from URL")
                return False, None, None
            
            print(f"📊 Tweet ID: {tweet_id}, Username: @{username}")
            
            # Use Thread Reader App
            print("🔄 Fetching thread using Thread Reader App...")
            return self._fetch_with_threadreader(twitter_url, tweet_id, username)
                
        except Exception as e:
            print(f"❌ Error fetching thread: {e}")
            import traceback
            traceback.print_exc()
            return False, None, None
    
    def _fetch_with_threadreader(self, twitter_url, tweet_id, username):
        """
        Fetch thread using Thread Reader App web scraping.
        
        Args:
            twitter_url (str): Twitter/X thread URL
            tweet_id (str): Tweet ID
            username (str): Username
            
        Returns:
            tuple: (success, content_file, thread_info)
        """
        try:
            # Thread Reader App URL
            threadreader_url = f"https://threadreaderapp.com/thread/{tweet_id}.html"
            
            print(f"📄 Fetching from Thread Reader App...")
            print(f"🌐 URL: {threadreader_url}")
            response = requests.get(
                threadreader_url,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
                },
                timeout=30
            )
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Extract tweet creation date from tweet ID (Snowflake ID)
                # Twitter IDs encode timestamp in first 41 bits
                try:
                    tweet_id_int = int(tweet_id)
                    twitter_epoch = 1288834974657  # Nov 4, 2010 in milliseconds
                    timestamp_ms = (tweet_id_int >> 22) + twitter_epoch
                    tweet_date = datetime.fromtimestamp(timestamp_ms / 1000)
                    print(f"📅 Tweet date: {tweet_date.strftime('%Y-%m-%d')}")
                except Exception as e:
                    print(f"⚠️  Could not extract date: {e}")
                    tweet_date = None
                
                # Try multiple selectors to find tweet content
                tweet_texts = []
                
                # Look for tweet content in various possible containers
                selectors = [
                    ('div', {'class': 'tweet-text'}),
                    ('div', {'class': 'content-tweet'}),
                    ('p', {'class': 'tweet'}),
                    ('div', {'class': 't-main'}),
                ]
                
                for tag, attrs in selectors:
                    elements = soup.find_all(tag, attrs)
                    if elements:
                        print(f"Found {len(elements)} elements with {tag} {attrs}")
                        for elem in elements:
                            text = elem.get_text(strip=True)
                            if text and len(text) > 20:
                                tweet_texts.append(text)
                        if tweet_texts:
                            break
                
                # If still no tweets, try getting all paragraphs from main content
                if not tweet_texts:
                    print("Trying to extract from main content area...")
                    main_content = soup.find('div', {'class': 'content'})
                    if main_content:
                        paragraphs = main_content.find_all('p')
                        for p in paragraphs:
                            text = p.get_text(strip=True)
                            if text and len(text) > 20:
                                tweet_texts.append(text)
                
                if tweet_texts:
                    thread_content = '\n\n'.join(tweet_texts)
                    
                    # Infer a better title from the content
                    print("🔍 Inferring title from thread content...")
                    inferred_title = self.infer_title_from_content(thread_content, username)
                    print(f"✨ Title: {inferred_title}")
                    
                    # Create thread info
                    thread_info = {
                        'title': inferred_title,
                        'uploader': username,
                        'url': twitter_url,
                        'created_time': tweet_date.isoformat() if tweet_date else None,  # ISO format for Notion
                        'type': 'twitter_thread'
                    }
                    
                    # Save to file
                    filename = f"{username}_{tweet_id}_thread.txt"
                    file_path = self.raw_dir / filename
                    
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(thread_content)
                    
                    print(f"✅ Thread saved: {len(tweet_texts)} tweets → {filename}")
                    return True, str(file_path), thread_info
                else:
                    print("❌ No tweet content found on Thread Reader App page")
                    return False, None, None
            else:
                print(f"❌ Failed to fetch Thread Reader App page: {response.status_code}")
                return False, None, None
                
        except Exception as e:
            print(f"❌ Error with Thread Reader App: {e}")
            import traceback
            traceback.print_exc()
            return False, None, None
