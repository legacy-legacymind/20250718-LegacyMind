#!/usr/bin/env python3
"""
Start the background embedding service with proper API key
"""
import os
import subprocess
import sys

def get_openai_key():
    """Get OpenAI API key from secure file"""
    try:
        with open('/Users/samuelatagana/LegacyMind_Vault/Secure/API_Keys.md', 'r') as f:
            content = f.read()
            
        # Find OpenAI key line (markdown format)
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if 'API Key' in line and '`sk-' in line:
                # Extract key from markdown backticks
                start = line.find('`sk-')
                end = line.find('`', start + 1)
                if start != -1 and end != -1:
                    key = line[start + 1:end]
                    if key.startswith('sk-'):
                        return key
                    
        return None
    except Exception as e:
        print(f"Error reading API key: {e}")
        return None

def main():
    # Get API key
    api_key = get_openai_key()
    if not api_key:
        print("Could not find OpenAI API key")
        sys.exit(1)
    
    print(f"Found API key: {api_key[:10]}...")
    
    # Set environment variable
    os.environ['OPENAI_API_KEY'] = api_key
    
    # Run background service
    if len(sys.argv) > 1 and sys.argv[1] == '--test':
        # Test mode - single run
        cmd = ['python3', 'background_embedding_service.py', '--single-run', '--batch-size', '3']
    else:
        # Continuous mode
        cmd = ['python3', 'background_embedding_service.py', '--batch-size', '10']
    
    print(f"Starting: {' '.join(cmd)}")
    subprocess.run(cmd)

if __name__ == "__main__":
    main()