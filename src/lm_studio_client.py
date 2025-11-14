"""
LM Studio API client for generating Reddit responses
"""

import requests
import json
import logging
import os

logger = logging.getLogger('RedditBot')


class LMStudioClient:
    """Handles interaction with local LM Studio API"""
    
    def __init__(self, api_url='http://localhost:1234/v1/chat/completions', 
                 model='meta-llama-3.1-8b-instruct',
                 temperature=0.7, max_tokens=500,
                 prompt_file='./prompts/response_generation.txt'):
        """
        Initialize LM Studio client.
        
        Args:
            api_url: LM Studio API endpoint (chat completions)
            model: Model name loaded in LM Studio
            temperature: Response creativity (0.0-1.0)
            max_tokens: Maximum response length (-1 for unlimited)
            prompt_file: Path to response generation prompt template (used as system message)
        """
        self.api_url = api_url
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.prompt_file = prompt_file
        
        # Load prompt template
        if os.path.exists(prompt_file):
            with open(prompt_file, 'r') as f:
                self.prompt_template = f.read()
            logger.info("Loaded LM Studio response generation prompt")
        else:
            logger.error(f"Prompt file not found: {prompt_file}")
            self.prompt_template = ""
    
    def generate_response(self, subreddit, title, content=''):
        """
        Generate a Reddit response using LM Studio.
        
        Args:
            subreddit: Subreddit name
            title: Thread title
            content: Thread content/body (optional)
        
        Returns:
            Generated response text, or None if failed
        """
        if not self.prompt_template:
            logger.error("No prompt template loaded")
            return None
        
        try:
            # Build system prompt and user message
            system_prompt = self._build_system_prompt()
            user_message = self._build_user_message(subreddit, title, content)
            
            logger.info(f"Generating response for r/{subreddit} thread: {title[:50]}...")
            
            # Call LM Studio API with chat completions format
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": user_message
                    }
                ],
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "stream": False
            }
            
            response = requests.post(
                self.api_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=60
            )
            
            if response.status_code != 200:
                logger.error(f"LM Studio API error: {response.status_code} - {response.text}")
                return None
            
            # Extract generated text from chat completions format
            result = response.json()
            generated_text = result.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
            
            if not generated_text:
                logger.warning("LM Studio returned empty response")
                return None
            
            logger.info(f"Generated response ({len(generated_text)} chars)")
            logger.debug(f"Response preview: {generated_text[:100]}...")
            
            return generated_text
            
        except requests.exceptions.Timeout:
            logger.error("LM Studio API timeout")
            return None
        except requests.exceptions.ConnectionError:
            logger.error("Cannot connect to LM Studio - ensure it's running")
            return None
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            return None
    
    def _build_system_prompt(self):
        """
        Build system prompt from template (without placeholders).
        
        Returns:
            System prompt string
        """
        # Remove the thread context section from system prompt
        lines = self.prompt_template.split('\n')
        system_lines = []
        skip_section = False
        
        for line in lines:
            if 'THREAD CONTEXT:' in line:
                skip_section = True
            if not skip_section:
                system_lines.append(line)
        
        return '\n'.join(system_lines).strip()
    
    def _build_user_message(self, subreddit, title, content):
        """
        Build user message with thread context.
        
        Args:
            subreddit: Subreddit name
            title: Thread title
            content: Thread content
        
        Returns:
            User message string
        """
        user_message = f"""Please write a helpful Reddit comment for this thread:

Subreddit: r/{subreddit}
Thread Title: {title}
Thread Content: {content if content else '[No body text]'}

Write a helpful, authentic response that naturally introduces LeaseWatch as a resource:"""
        
        return user_message
    
    def test_connection(self):
        """
        Test if LM Studio API is accessible.
        
        Returns:
            True if accessible, False otherwise
        """
        try:
            # Try to get models endpoint (if available)
            test_url = self.api_url.replace('/chat/completions', '/models')
            response = requests.get(test_url, timeout=5)
            
            if response.status_code == 200:
                logger.info("LM Studio API connection successful")
                return True
            else:
                # Try simple chat completion
                payload = {
                    "model": self.model,
                    "messages": [
                        {"role": "user", "content": "Hi"}
                    ],
                    "max_tokens": 5,
                    "stream": False
                }
                response = requests.post(self.api_url, json=payload, timeout=10)
                
                if response.status_code == 200:
                    logger.info("LM Studio API connection successful")
                    return True
                else:
                    logger.warning(f"LM Studio API test failed: {response.status_code}")
                    return False
                    
        except requests.exceptions.ConnectionError:
            logger.error("Cannot connect to LM Studio - ensure it's running on localhost:1234")
            return False
        except Exception as e:
            logger.error(f"Error testing LM Studio API: {str(e)}")
            return False
    
    def validate_response(self, response_text):
        """
        Validate generated response meets quality standards.
        
        Args:
            response_text: Generated response
        
        Returns:
            True if valid, False otherwise
        """
        if not response_text:
            return False
        
        # Check minimum length
        if len(response_text) < 50:
            logger.warning("Response too short")
            return False
        
        # Check maximum length
        if len(response_text) > 2000:
            logger.warning("Response too long")
            return False
        
        # Check for placeholder text (common LLM issue)
        placeholder_phrases = [
            '[insert',
            '[your',
            '[company',
            'PLACEHOLDER',
            '{{',
            '}}'
        ]
        
        for phrase in placeholder_phrases:
            if phrase.lower() in response_text.lower():
                logger.warning(f"Response contains placeholder: {phrase}")
                return False
        
        return True
