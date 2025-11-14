"""
Gemini CLI integration for discovering relevant Reddit threads
"""

import subprocess
import json
import logging
import os

logger = logging.getLogger('RedditBot')


class GeminiClient:
    """Handles interaction with Gemini CLI for thread discovery"""
    
    def __init__(self, cli_path='gemini', prompt_file='./prompts/gemini_discovery.txt'):
        """
        Initialize Gemini client.
        
        Args:
            cli_path: Path to gemini CLI command
            prompt_file: Path to discovery prompt template
        """
        self.cli_path = cli_path
        self.prompt_file = prompt_file
        
        # Load prompt template
        if os.path.exists(prompt_file):
            with open(prompt_file, 'r') as f:
                self.prompt_template = f.read()
            logger.info("Loaded Gemini discovery prompt")
        else:
            logger.error(f"Prompt file not found: {prompt_file}")
            self.prompt_template = ""
    
    def discover_threads(self):
        """
        Use Gemini CLI to discover relevant Reddit threads.
        
        Returns:
            List of thread dictionaries with keys: subreddit, title, keywords, 
            relevance_score, reason
        """
        if not self.prompt_template:
            logger.error("No prompt template loaded")
            return []
        
        try:
            logger.info("Querying Gemini CLI for relevant threads...")
            
            # Execute Gemini CLI command
            result = subprocess.run(
                [self.cli_path],
                input=self.prompt_template,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                logger.error(f"Gemini CLI error: {result.stderr}")
                return []
            
            # Parse response
            response_text = result.stdout.strip()
            logger.debug(f"Gemini raw response: {response_text[:500]}...")
            
            # Try to extract JSON from response
            threads = self._parse_gemini_response(response_text)
            
            logger.info(f"Gemini discovered {len(threads)} relevant threads")
            return threads
            
        except subprocess.TimeoutExpired:
            logger.error("Gemini CLI timeout")
            return []
        except Exception as e:
            logger.error(f"Error querying Gemini: {str(e)}")
            return []
    
    def _parse_gemini_response(self, response_text):
        """
        Parse JSON from Gemini response.
        
        Args:
            response_text: Raw text from Gemini CLI
        
        Returns:
            List of thread dictionaries
        """
        try:
            # Try to find JSON in response (Gemini might add text before/after)
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            
            if start_idx == -1 or end_idx == 0:
                logger.warning("No JSON found in Gemini response")
                return []
            
            json_str = response_text[start_idx:end_idx]
            data = json.loads(json_str)
            
            # Extract threads array
            threads = data.get('threads', [])
            
            # Validate thread structure
            valid_threads = []
            for thread in threads:
                if self._validate_thread(thread):
                    valid_threads.append(thread)
                else:
                    logger.warning(f"Invalid thread structure: {thread}")
            
            return valid_threads
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini JSON: {str(e)}")
            logger.debug(f"Response text: {response_text}")
            return []
    
    def _validate_thread(self, thread):
        """
        Validate thread dictionary has required fields.
        
        Args:
            thread: Thread dictionary
        
        Returns:
            True if valid, False otherwise
        """
        required_fields = ['subreddit', 'title']
        return all(field in thread for field in required_fields)
    
    def test_connection(self):
        """
        Test if Gemini CLI is accessible.
        
        Returns:
            True if accessible, False otherwise
        """
        try:
            result = subprocess.run(
                [self.cli_path, '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                logger.info("Gemini CLI connection successful")
                return True
            else:
                logger.warning(f"Gemini CLI test failed: {result.stderr}")
                return False
                
        except FileNotFoundError:
            logger.error(f"Gemini CLI not found at: {self.cli_path}")
            return False
        except Exception as e:
            logger.error(f"Error testing Gemini CLI: {str(e)}")
            return False
