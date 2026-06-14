#!/usr/bin/env python3
"""
Phase 4 SSM Leap Completion Script
Attempts to load Mamba-3:2.8b model and validate performance targets
"""

import asyncio
import time
import logging
import sys
import os
from typing import Dict, Any

# Add the phase4-ssm-leap directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'phase4-ssm-leap', 'integrations'))

# Import the adapter (note: filename uses hyphens)
import importlib.util
spec = importlib.util.spec_from_file_location(
    "mamba_intent_judge_adapter", 
    os.path.join(os.path.dirname(__file__), 'phase4-ssm-leap', 'integrations', 'mamba-intent-judge-adapter.py')
)
mamba_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mamba_module)

MambaIntentJudgeAdapter = mamba_module.MambaIntentJudgeAdapter
create_mamba_intent_judge_adapter = mamba_module.create_mamba_intent_judge_adapter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def attempt_mamba_loading():
    """
    Attempt to load and test Mamba-3:2.8b model for Phase 4 SSM Leap
    """
    logger.info("=== Phase 4 SSM Leap Completion Attempt ==")
    logger.info("Target: Mamba-3:2.8b as Intent Judge backend")
    logger.info("Goal: <200ms trigger-to-thought latency (4.1x faster than gemma4)")
    
    # Create adapter
    adapter = create_mamba_intent_judge_adapter()
    
    # Step 1: Load model
    logger.info("Step 1: Loading Mamba-3:2.8b model...")
    load_success = await adapter.load_model()
    
    if not load_success:
        logger.error("FAILED: Could not load Mamba-3:2.8b model")
        logger.info("This indicates the model may not be available in the current environment")
        logger.info("Next steps would involve:")
        logger.info("  1. Checking Ollama/HuggingFace for mamba-3:2.8b availability")
        logger.info("  2. Pulling the model if available")
        logger.info("  3. Or using an alternative SSM approach if Mamba-3:2.8b is not accessible")
        return False
    
    logger.info("SUCCESS: Mamba-3:2.8b model loaded")
    
    # Step 2: Warmup and performance validation
    logger.info("Step 2: Warming up model and validating performance...")
    warmup_success = await adapter.warmup(num_iterations=5)
    
    if not warmup_success:
        logger.warning("Warmup completed but performance targets may not be met")
    else:
        logger.info("SUCCESS: Model warmed up and performance targets met")
    
    # Step 3: Test encoding performance
    logger.info("Step 3: Testing encoding performance...")
    test_inputs = [
        "Analyze current market conditions for AI investment opportunities",
        "What is the optimal workload distribution for LLM inference?",
        "Detect anomalies in system performance metrics",
        "Predict next 24-hour trend for cryptocurrency markets",
        "Evaluate risk factors for tech sector allocation"
    ]
    
    encoding_results = []
    for i, test_input in enumerate(test_inputs, 1):
        logger.info(f"  Testing input {i}/{len(test_inputs)}: '{test_input[:50]}...'")
        result = await adapter.encode_intent(test_input)
        encoding_results.append(result)
        
        if result.get("status") == "success":
            encoding_time = result.get("encoding_time_ms", 0)
            logger.info(f"    Encoding time: {encoding_time:.2f}ms")
        else:
            logger.error(f"    Encoding failed: {result.get('error', 'Unknown error')}")
    
    # Step 4: Get final performance metrics
    logger.info("Step 4: Calculating final performance metrics...")
    metrics = adapter.get_performance_metrics()
    
    logger.info(f"Performance Metrics:")
    logger.info(f"  Average encoding time: {metrics.get('avg_encoding_time_ms', 0):.2f}ms")
    logger.info(f"  Min encoding time: {metrics.get('min_encoding_time_ms', 0):.2f}ms")
    logger.info(f"  Max encoding time: {metrics.get('max_encoding_time_ms', 0):.2f}ms")
    logger.info(f"  Speedup vs gemma4: {metrics.get('speedup_vs_gemma4', 0):.2f}x")
    logger.info(f"  Performance target met: {metrics.get('performance_target_met', False)}")
    logger.info(f"  Ready for production: {adapter.is_ready_for_production()}")
    
    # Step 5: Summary
    logger.info("=== Phase 4 SSM Leap Completion Summary ===")
    if adapter.is_ready_for_production():
        logger.info("✅ SUCCESS: Phase 4 SSM Leap Track 1 is COMPLETE")
        logger.info("   Mamba-3:2.8b loaded, warmed up, and meeting performance targets")
        logger.info("   Ready for production use as Intent Judge backend")
        return True
    else:
        logger.info("⚠️  PARTIAL: Infrastructure ready but performance validation needed")
        logger.info("   Mamba-3:2.8b model access confirmed")
        logger.info("   Adapter framework functional")
        logger.info("   Ready for model acquisition and benchmarking")
        return False

async def main():
    """Main execution function"""
    try:
        success = await attempt_mamba_loading()
        return 0 if success else 1
    except Exception as e:
        logger.error(f"Phase 4 SSM Leap completion failed with error: {e}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)