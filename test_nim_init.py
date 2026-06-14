#!/usr/bin/env python3
"""Test NIM client initialization with API key"""

import sys
import os
sys.path.append('/home/dario/.openclaw/workspace/nim_integration')

# Test with API key set
os.environ['NVIDIA_API_KEY'] = '***'

try:
    from nim_client_enhanced import NVIDIANIMClient
    print("✅ Import successful")
    
    # Test initialization
    client = NVIDIANIMClient()
    print(f"✅ Client created")
    print(f"   Is available: {client.is_available}")
    print(f"   Is ready: {client.is_ready()}")
    
    if client.is_available:
        print(f"✅ NIM Client initialized successfully!")
        print(f"   Model: {client.selected_model_info['display_name']}")
        print(f"   Model key: {client.selected_model}")
    else:
        print("❌ NIM Client not available")
        
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()