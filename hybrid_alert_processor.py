#!/usr/bin/env python3
"""
Hybrid Alert Processor for Phase 4 SSM Leap
Combines fast Mamba-3:2.8b alerts with NVIDIA NIM deep analysis
"""

import os
import time
import json
import logging
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

# Import our NIM client
import sys
sys.path.append('/home/dario/.openclaw/workspace/nim_integration')
from nim_client_clean import NVIDIANIMClient

# Import our existing Mamba system components
sys.path.append('/home/dario/.openclaw/workspace')
try:
    from deploy-phase4-oew-live import Phase4OEWLiveDeployer
    MAMBA_AVAILABLE = True
except ImportError as e:
    MAMBA_AVAILABLE = False
    print(f"Warning: Could not import Mamba components: {e}")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/dario/.openclaw/workspace/nim_integration/logs/hybrid_alert.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class HybridAlertProcessor:
    """Hybrid alert processor combining fast local analysis with deep NIM analysis"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Initialize Mamba-3:2.8b (fast path) - if available
        self.mamba_deployer = None
        self.mamba_ready = False
        if MAMBA_AVAILABLE:
            try:
                self.mamba_deployer = Phase4OEWLiveDeployer()
                # Note: We won't initialize here to avoid loading model until needed
                self.logger.info("✅ Mamba-3:2.8b deployer ready (lazy initialized)")
            except Exception as e:
                self.logger.error(f"❌ Failed to initialize Mamba deployer: {e}")
        
        # Initialize NVIDIA NIM (deep path)
        self.nim_client = NVIDIANIMClient(api_key=os.getenv('NVIDIA_API_KEY'))
        if self.nim_client.is_ready():
            self.logger.info("✅ NVIDIA NIM client ready for deep analysis")
        else:
            self.logger.warning("⚠️ NVIDIA NIM client not available - fast path only")
        
        # Alert routing rules - which events get deep analysis
        self.deep_analysis_triggers = {
            'vendors': {'AWS', 'Azure', 'Google Cloud', 'GitHub', 'Stripe', 'PayPal', 
                       'Binance', 'Coinbase', 'Ledger', 'Tesla', 'Apple', 'Microsoft'},
            'event_types': ['Service Disruption', 'Outage', 'Failure', 'Breach', 
                          'Regulatory Change', 'Merger', 'Acquisition', 'Bankruptcy'],
            'severities': ['CRITICAL', 'MAJOR'],
            # Complex events that benefit from deep analysis
            'complex_patterns': [
                'multi-service', 'cascading', 'systemic', 'regulatory', 
                'geopolitical', 'financial', 'cyber-attack', 'supply-chain'
            ]
        }
        
        # Statistics tracking
        self.stats = {
            'total_processed': 0,
            'fast_path_only': 0,
            'deep_path_used': 0,
            'avg_fast_latency_ms': 0.0,
            'avg_deep_latency_ms': 0.0
        }
        
        self.logger.info("🚀 Hybrid Alert Processor initialized")
    
    def _should_use_deep_analysis(self, event_data: Dict[str, Any]) -> bool:
        """Determine if an event should receive deep NIM analysis"""
        if not self.nim_client.is_ready():
            return False
            
        vendor = event_data.get('vendor', '').lower()
        event_type = event_data.get('type', '').lower()
        severity = event_data.get('severity', '').lower()
        description = event_data.get('description', '').lower()
        
        # Check vendor
        if any(v.lower() in vendor for v in self.deep_analysis_triggers['vendors']):
            return True
            
        # Check event type
        if any(t.lower() in event_type for t in self.deep_analysis_triggers['event_types']):
            return True
            
        # Check severity
        if severity in [s.lower() for s in self.deep_analysis_triggers['severities']]:
            return True
            
        # Check for complex patterns in description
        if any(pattern in description for pattern in self.deep_analysis_triggers['complex_patterns']):
            return True
            
        # Default: use deep analysis for CRITICAL/MAJOR events from major vendors
        # This ensures we get deep analysis for high-impact events
        return severity in ['critical', 'major'] and len(vendor) > 3
    
    async def process_alert_hybrid(
        self, 
        event_data: Dict[str, Any],
        generate_immediate_alert: bool = True,
        generate_enriched_followup: bool = True
    ) -> Dict[str, Any]:
        """
        Process a market event using the hybrid approach
        
        Returns:
            Dictionary containing both immediate alert (if requested) 
            and enriched follow-up analysis (if requested)
        """
        start_time = time.time()
        self.stats['total_processed'] += 1
        
        result = {
            'event_id': f"hybrid_{int(time.time())}_{self.stats['total_processed']}",
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'original_event': event_data,
            'immediate_alert': None,
            'enriched_analysis': None,
            'processing_mode': 'unknown',
            'total_latency_ms': 0,
            'status': 'processing'
        }
        
        try:
            vendor = event_data.get('vendor', 'Unknown')
            event_type = event_data.get('type', 'Unknown')
            severity = event_data.get('severity', 'Unknown')
            
            self.logger.info(
                f"🔄 Processing hybrid alert: {severity} {vendor} {event_type}"
            )
            
            # STEP 1: FAST PATH - Mamba-3:2.8b Immediate Analysis
            fast_start = time.time()
            immediate_alert = None
            
            if generate_immediate_alert and self.mamba_deployer:
                try:
                    # Lazy initialize Mamba if needed
                    if not self.mamba_ready:
                        self.logger.info("🚀 Initializing Mamba-3:2.8b for fast path...")
                        init_success = await self.mamba_deployer.initialize()
                        if init_success:
                            self.mamba_ready = True
                            self.logger.info("✅ Mamba-3:2.8b initialized for fast path")
                        else:
                            self.logger.warning("⚠️ Mamba initialization failed - fast path degraded")
                    
                    if self.mamba_ready:
                        # Process event with Mamba for fast intent classification
                        mamba_result = await self.mamba_deployer.process_live_pulsewatch_event(event_data)
                        
                        fast_end = time.time()
                        fast_latency_ms = (fast_end - fast_start) * 1000
                        
                        # Update stats
                        self._update_fast_latency_stats(fast_latency_ms)
                        
                        # Create immediate alert
                        immediate_alert = {
                            'alert_type': 'IMMEDIATE',
                            'alert_id': f"imm_{int(time.time())}",
                            'timestamp': datetime.now(timezone.utc).isoformat(),
                            'vendor': vendor,
                            'event_type': event_type,
                            'severity': severity,
                            'description': event_data.get('description', '')[:200],
                            'confidence': event_data.get('confidence', 0.0),
                            'mamba_processing_ms': round(fast_latency_ms, 2),
                            'mamba_intent_latency_ms': mamba_result.get('phase4_performance', {}).get('intent_judgment_latency_ms', 0),
                            'alert_message': self._format_immediate_alert(event_data, mamba_result),
                            'processing_path': 'FAST_PATH_MAMBA'
                        }
                        
                        self.logger.info(
                            f"⚡ Fast path alert generated in {fast_latency_ms:.0f}ms "
                            f"(Mamba intent: {mamba_result.get('phase4_performance', {}).get('intent_judgment_latency_ms', 0):.0f}ms)"
                        )
                    else:
                        # Fallback if Mamba not available
                        fast_end = time.time()
                        fast_latency_ms = (fast_end - fast_start) * 1000
                        immediate_alert = self._create_fallback_immediate_alert(event_data)
                        
                except Exception as e:
                    fast_end = time.time()
                    fast_latency_ms = (fast_end - fast_start) * 1000
                    self.logger.error(f"❌ Fast path error after {fast_latency_ms:.0f}ms: {e}")
                    immediate_alert = self._create_fallback_immediate_alert(event_data)
            else:
                # Skip fast path if not requested or Mamba unavailable
                fast_end = time.time()
                fast_latency_ms = (fast_end - fast_start) * 1000
                if not generate_immediate_alert:
                    self.logger.info("⏭️  Skipping immediate alert (not requested)")
                else:
                    self.logger.warning("⚠️ Fast path skipped - Mamba not available")
            
            # STEP 2: DEEP PATH - NVIDIA NIM Enriched Analysis (if triggered)
            enriched_analysis = None
            deep_used = False
            
            if generate_enriched_followup and self._should_use_deep_analysis(event_data):
                try:
                    self.logger.info("🧠 Initiating deep analysis path...")
                    deep_start = time.time()
                    
                    # Perform deep analysis with NVIDIA NIM
                    nim_result = await asyncio.get_event_loop().run_in_executor(
                        None,  # Use default executor
                        self.nim_client.analyze_market_event_deep,
                        event_data,
                        "comprehensive"
                    )
                    
                    deep_end = time.time()
                    deep_latency_ms = (deep_end - deep_start) * 1000
                    
                    # Update stats
                    self._update_deep_latency_stats(deep_latency_ms)
                    
                    if nim_result.get('status') == 'success':
                        enriched_analysis = {
                            'analysis_type': 'ENRICHED_FOLLOW_UP',
                            'analysis_id': f"enr_{int(time.time())}",
                            'timestamp': datetime.now(timezone.utc).isoformat(),
                            'vendor': vendor,
                            'event_type': event_type,
                            'severity': severity,
                            'original_description': event_data.get('description', ''),
                            'nim_processing_ms': round(deep_latency_ms, 2),
                            'nim_model_used': nim_result.get('model_used'),
                            'nim_token_usage': nim_result.get('token_usage', {}),
                            'deep_analysis': nim_result.get('raw_analysis', ''),
                            'structured_insights': nim_result.get('structured_insights', {}),
                            'confidence_level': self._extract_confidence(nim_result.get('raw_analysis', '')),
                            'processing_path': 'DEEP_PATH_NIM'
                        }
                        
                        deep_used = True
                        self.stats['deep_path_used'] += 1
                        
                        self.logger.info(
                            f"🧠 Deep analysis completed in {deep_latency_ms:.0f}ms "
                            f"({nim_result.get('token_usage', {}).get('total_tokens', 0)} tokens)"
                        )
                    else:
                        self.logger.error(
                            f"❌ Deep analysis failed: {nim_result.get('error', 'Unknown error')}"
                        )
                        
                except Exception as e:
                    deep_end = time.time()
                    deep_latency_ms = (deep_end - deep_start) * 1000
                    self.logger.error(f"❌ Deep path error after {deep_latency_ms:.0f}ms: {e}")
            
            # Determine processing mode
            if immediate_alert and enriched_analysis:
                processing_mode = "HYBRID_FULL"
                self.stats['deep_path_used'] += 1  # Count as deep path used
            elif immediate_alert:
                processing_mode = "FAST_PATH_ONLY"
                self.stats['fast_path_only'] += 1
            elif enriched_analysis:
                processing_mode = "DEEP_PATH_ONLY"  # Rare case
            else:
                processing_mode = "FAILED"
            
            # Finalize result
            end_time = time.time()
            total_latency_ms = (end_time - start_time) * 1000
            
            result.update({
                'immediate_alert': immediate_alert,
                'enriched_analysis': enriched_analysis,
                'processing_mode': processing_mode,
                'total_latency_ms': round(total_latency_ms, 2),
                'status': 'completed' if (immediate_alert or enriched_analysis) else 'failed'
            })
            
            self.logger.info(
                f"✅ Hybrid alert processing completed in {total_latency_ms:.0f}ms "
                f"[{processing_mode}] - Event: {severity} {vendor} {event_type}"
            )
            
            return result
            
        except Exception as e:
            end_time = time.time()
            total_latency_ms = (end_time - start_time) * 1000
            
            self.logger.error(
                f"❌ Hybrid alert processing failed after {total_latency_ms:.0f}ms: {e}"
            )
            
            result.update({
                'status': 'error',
                'error': str(e),
                'total_latency_ms': round(total_latency_ms, 2),
                'processing_mode': 'ERROR'
            })
            
            return result
    
    def _update_fast_latency_stats(self, latency_ms: float):
        """Update fast path latency statistics"""
        current_avg = self.stats['avg_fast_latency_ms']
        count = max(1, self.stats['total_processed'] - self.stats['deep_path_used'])  # Approximate
        new_avg = ((current_avg * (count - 1)) + latency_ms) / count if count > 0 else latency_ms
        self.stats['avg_fast_latency_ms'] = new_avg
    
    def _update_deep_latency_stats(self, latency_ms: float):
        """Update deep path latency statistics"""
        current_avg = self.stats['avg_deep_latency_ms']
        count = max(1, self.stats['deep_path_used'])
        new_avg = ((current_avg * (count - 1)) + latency_ms) / count if count > 0 else latency_ms
        self.stats['avg_deep_latency_ms'] = new_avg
    
    def _format_immediate_alert(self, event_data: Dict[str, Any], mamba_result: Dict) -> str:
        """Format immediate alert message"""
        vendor = event_data.get('vendor', 'Unknown')
        event_type = event_data.get('type', 'Unknown')
        severity = event_data.get('severity', 'Unknown')
        confidence = event_data.get('confidence', 0.0)
        intent_latency = mamba_result.get('phase4_performance', {}).get('intent_judgment_latency_ms', 0)
        
        return (
            f"[PHASE4-ALERT] {severity} {vendor} {event_type} | "
            f"Confidence: {confidence:.0f}% | "
            f"Mamba Intent: {intent_latency:.0f}ms | "
            f"{event_data.get('description', '')[:100]}..."
        )
    
    def _create_fallback_immediate_alert(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a fallback immediate alert when Mamba is unavailable"""
        return {
            'alert_type': 'IMMEDIATE_FALLBACK',
            'alert_id': f"imm_fb_{int(time.time())}",
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'vendor': event_data.get('vendor', 'Unknown'),
            'event_type': event_data.get('type', 'Unknown'),
            'severity': event_data.get('severity', 'Unknown'),
            'description': event_data.get('description', '')[:200],
            'confidence': event_data.get('confidence', 0.0),
            'mamba_processing_ms': 0,
            'mamba_intent_latency_ms': 0,
            'alert_message': f"[FALLBACK] {event_data.get('severity', 'UNKNOWN')} {event_data.get('vendor', 'UNKNOWN')} {event_data.get('type', 'EVENT')}: {event_data.get('description', '')[:100]}...",
            'processing_path': 'FALLBACK_PATH'
        }
    
    def _extract_confidence(self, text: str) -> Optional[float]:
        """Extract confidence level from analysis text"""
        import re
        # Look for confidence patterns
        confidence_patterns = [
            r'confidence[:\s]+(\d+(?:\.\d+)?)%',
            r'(\d+(?:\.\d+)?)%\s*confidence',
            r'certainty[:\s]+(\d+(?:\.\d+)?)%'
        ]
        
        for pattern in confidence_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    continue
        return None
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get processing statistics"""
        return self.stats.copy()
    
    def reset_statistics(self):
        """Reset processing statistics"""
        self.stats = {
            'total_processed': 0,
            'fast_path_only': 0,
            'deep_path_used': 0,
            'avg_fast_latency_ms': 0.0,
            'avg_deep_latency_ms': 0.0
        }
        self.logger.info("📊 Statistics reset")

def test_hybrid_processor():
    """Test the hybrid alert processor"""
    print("🧪 Testing Hybrid Alert Processor")
    print("=" * 50)
    
    processor = HybridAlertProcessor()
    
    # Test events
    test_events = [
        {
            'vendor': 'AWS',
            'type': 'S3 Service Disruption',
            'severity': 'CRITICAL',
            'description': 'US-EAST-1 region experiencing widespread S3 service disruption affecting storage operations',
            'confidence': 95.0
        },
        {
            'vendor': 'Stripe',
            'type': 'Payment Processing Outage',
            'severity': 'CRITICAL',
            'description': 'Global payment processing experiencing complete outage affecting all transactions',
            'confidence': 96.0
        },
        {
            'vendor': 'GitHub',
            'type': 'API Authentication Failure',
            'severity': 'CRITICAL', 
            'description': 'Global API authentication service experiencing complete outage affecting all git operations',
            'confidence': 98.0
        }
    ]
    
    print(f"📊 NIM Client Ready: {processor.nim_client.is_ready()}")
    print(f"🚀 Mamba Ready: {processor.mamba_ready} (will initialize on first use)")
    print(f"🔧 Deep Analysis Triggers: {len(processor.deep_analysis_triggers['vendors'])} vendors")
    print("")
    
    # Process test events
    for i, event in enumerate(test_events, 1):
        print(f"\n📝 Test Event {i}: {event['severity']} {event['vendor']} {event['type']}")
        print(f"   Description: {event['description'][:60]}...")
        
        # Process with hybrid approach
        result = asyncio.run(processor.process_alert_hybrid(
            event,
            generate_immediate_alert=True,
            generate_enriched_followup=True
        ))
        
        print(f"   ⚡ Mode: {result['processing_mode']}")
        print(f"   ⏱️  Total Latency: {result['total_latency_ms']:.0f}ms")
        
        if result['immediate_alert']:
            print(f"   🚨 Immediate Alert: {result['immediate_alert']['alert_message'][:80]}...")
        
        if result['enriched_analysis']:
            print(f"   🧠 Enriched Analysis: {result['enriched_analysis']['deep_analysis'][:100]}...")
            print(f"   🔢 NIM Tokens: {result['enriched_analysis']['nim_token_usage'].get('total_tokens', 0)}")
    
    # Show statistics
    print(f"\n📈 Processing Statistics:")
    stats = processor.get_statistics()
    for key, value in stats.items():
        if isinstance(value, float):
            print(f"   {key}: {value:.2f}")
        else:
            print(f"   {key}: {value}")
    
    return processor

if __name__ == "__main__":
    # Run test if executed directly
    test_hybrid_processor()
