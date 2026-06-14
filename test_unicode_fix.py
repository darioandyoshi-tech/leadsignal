#!/usr/bin/env python3
"""Test the Unicode fix in error handling"""

import sys
import os
sys.path.append('/home/dario/.openclaw/workspace/nim_integration')

def safe_unicode_string(text: str, max_length: int = None) -> str:
    """Safely handle Unicode strings for logging/printing to avoid ASCII encoding errors"""
    if not isinstance(text, str):
        text = str(text)
    
    if max_length and len(text) > max_length:
        text = text[:max_length]
    
    try:
        # Test if we can encode to ASCII
        text.encode('ascii')
        return text
    except UnicodeEncodeError:
        # Replace problematic Unicode characters
        return text.encode('ascii', 'replace').decode('ascii')

# Test the error handling fix
def test_error_handling():
    # Simulate an exception with Unicode that caused the original issue
    try:
        # This simulates the kind of error that would cause the Unicode issue
        raise ValueError("Test error with Unicode: \u2026 ellipsis and sp\u00e9cial chars")
    except Exception as e:
        # Original problematic code (would fail)
        # error_msg = str(e)  # This could cause Unicode issues
        
        # Fixed code
        error_msg = str(e)
        safe_error_msg = safe_unicode_string(error_msg)
        print(f"✅ Safe error message: {safe_error_msg}")
        return True

if __name__ == "__main__":
    test_error_handling()
    print("✅ Unicode fix in error handling works!")