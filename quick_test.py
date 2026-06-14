#!/usr/bin/env python3
"""Quick test to verify the enhanced NIM client works"""

import sys
import os
sys.path.append('/home/dario/.openclaw/workspace/nim_integration')

# Test the imports
try:
    from nim_client import NVIDIANIMClient, get_available_financial_models, select_optimal_financial_model
    print("✅ Imports successful")
except Exception as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)

# Test model information
try:
    models = get_available_financial_models()
    print(f"✅ Available financial models: {list(models.keys())}")
    
    for key, info in models.items():
        print(f"   {key}: {info['display_name']} ({info['expected_latency_ms']}ms)")
        
except Exception as e:
    print(f"❌ Model info failed: {e}")
    sys.exit(1)

# Test model selection
try:
    model1 = select_optimal_financial_model("IMMEDIATE", "LOW", 500)
    model2 = select_optimal_financial_model("STANDARD", "MEDIUM", None)
    model3 = select_optimal_financial_model("STANDARD", "HIGH", 2000)
    
    print(f"✅ Model selection tests:")
    print(f"   IMMEDIATE/LOW/500ms → {model1}")
    print(f"   STANDARD/MEDIUM/None → {model2}")
    print(f"   STANDARD/HIGH/2000ms → {model3}")
    
except Exception as e:
    print(f"❌ Model selection failed: {e}")
    sys.exit(1)

print("🎉 All basic tests passed!")