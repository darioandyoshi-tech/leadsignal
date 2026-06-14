#!/usr/bin/env python3
"""
NVIDIA NIM Client for Phase 4 SSM Leap Hybrid System
Handles secure communication with NVIDIA NIM API for deep market analysis
"""

import os
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
def safe_unicode_string(text: str, max_length: int = None) -> str:
    """Safely handle Unicode strings for logging/printing to avoid ASCII encoding errors"""
    if not isinstance(text, str):
        text = str(text)
    try:
        # Test if we can encode to ASCII
        text.encode('ascii')
        return text
    except UnicodeEncodeError:
        # Replace problematic Unicode characters
        return text.encode('ascii', 'replace').decode('ascii')

import time
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from pathlib import Path
import sys

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

class NVIDIANIMClient:
    """Client for interacting with NVIDIA NIM API for deep market analysis"""
    
    def __init__(self, api_key: Optional[str] = None):
        # Setup logging first
        self.logger = logging.getLogger(__name__)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
        
        self.api_key = api_key or os.getenv('NVIDIA_API_KEY')
        self.client = None
        self.is_available = False
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize the NVIDIA NIM client"""
        if not OPENAI_AVAILABLE:
            self.logger.warning("OpenAI package not available")
            return
            
        if not self.api_key:
            self.logger.warning("NVIDIA API key not provided")
            return
            
        try:
            self.client = OpenAI(
                base_url='https://integrate.api.nvidia.com/v1',
                api_key=self.api_key,
                timeout=30.0  # 30 second timeout for API calls
            )
            self.is_available = True
            self.logger.info("✅ NVIDIA NIM client initialized successfully")
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize NVIDIA NIM client: {e}")
            self.is_available = False
    
    def is_ready(self) -> bool:
        """Check if the NIM client is ready for use"""
        return self.is_available and self.client is not None
    
    def analyze_market_event_deep(
        self, 
        event_data: Dict[str, Any], 
        analysis_type: str = "comprehensive"
    ) -> Dict[str, Any]:
        """
        Perform deep market analysis using NVIDIA NIM
        
        Args:
            event_data: Market event information from PulseWatch
            analysis_type: Type of analysis to perform
            
        Returns:
            Deep analysis results including insights, recommendations, and confidence
        """
        if not self.is_ready():
            return {
                "status": "error",
                "error": "NVIDIA NIM client not available",
                "fallback_suggested": True
            }
        
        start_time = time.time()
        
        try:
            # Prepare the analysis prompt based on event data and type
            prompt = self._build_analysis_prompt(event_data, analysis_type)
            
            self.logger.info(f"🧠 Starting deep market analysis: {analysis_type}")
            self.logger.debug(f"📝 Prompt length: {len(prompt)} characters")
            
            # Call NVIDIA NIM API
            response = self.client.chat.completions.create(
                model='nvidia/llama-3.1-nemotron-nano-8b-v1',  # Start with efficient model
                messages=[
                    {
                        "role": "system", 
                        "content": "You are an expert financial market analyst specializing in real-time event impact assessment, arbitrage opportunity identification, and trading strategy recommendations. Provide concise, actionable insights with clear confidence levels."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                max_tokens=500,
                temperature=0.2,  # Low temperature for consistent, factual analysis
                top_p=0.9
            )
            
            end_time = time.time()
            processing_time_ms = (end_time - start_time) * 1000
            
            # Extract and structure the response
            raw_content = response.choices[0].message.content.strip()
            
            analysis_result = {
                "status": "success",
                "analysis_type": analysis_type,
                "processing_time_ms": round(processing_time_ms, 2),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "model_used": "nvidia/llama-3.1-nemotron-nano-8b-v1",
                "raw_analysis": raw_content,
                "token_usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                },
                "structured_insights": self._structure_analysis(
                    raw_content,
                    event_data
                )
            }
            
            # Log with safe unicode handling
            safe_analysis = safe_unicode_string(raw_content, 100)
            self.logger.info(
                f"✅ Deep analysis completed in {processing_time_ms:.0f}ms "
                f"({response.usage.total_tokens} tokens)"
            )
            self.logger.debug(f"📝 Analysis preview: {safe_analysis}")
            
            return analysis_result
            
        except Exception as e:
            end_time = time.time()
            processing_time_ms = (end_time - start_time) * 1000
            
            # Safe error message for logging
            safe_error = safe_unicode_string(str(e))
            self.logger.error(
                f"❌ Deep analysis failed after {processing_time_ms:.0f}ms: {safe_error}"
            )
            
            return {
                "status": "error",
                "error": safe_unicode_string(str(e)),
                "processing_time_ms": round(processing_time_ms, 2),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "fallback_suggested": True
            }
    
    def _build_analysis_prompt(self, event_data: Dict[str, Any], analysis_type: str) -> str:
        """Build analysis prompt based on event data and requested analysis type"""
        
        vendor = event_data.get('vendor', 'Unknown')
        event_type = event_data.get('type', 'Unknown')
        severity = event_data.get('severity', 'Unknown')
        description = event_data.get('description', '')
        confidence = event_data.get('confidence', 0.0)
        
        base_context = f"""
MARKET EVENT ALERT:
- Vendor: {vendor}
- Event Type: {event_type}
- Severity: {severity}
- Description: {description}
- Confidence: {confidence:.1f}%
- Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}
"""
        
        if analysis_type == "comprehensive":
            prompt = f"""{base_context}

Please provide a comprehensive market analysis including:

1. **IMMEDIATE IMPACT ASSESSMENT** (0-4 hours)
   - Direct affected parties and sectors
   - Immediate trading implications
   - Liquidity and volatility expectations

2. **SHORT-TERM IMPACT** (4-24 hours)  
   - Cascading effects and secondary impacts
   - Market sentiment shifts
   - Arbitrage opportunity identification

3. **MEDIUM-TERM OUTLOOK** (1-7 days)
   - Potential resolution scenarios
   - Longer-term positioning considerations
   - Risk factors to monitor

4. **TRADING RECOMMENDATIONS**
   - Specific actionable strategies (if applicable)
   - Risk management considerations
   - Entry/exit timing considerations
   - Position sizing guidance

5. **CONFIDENCE & UNCERTAINTY**
   - Analysis confidence level (0-100%)
   - Key uncertainties and monitoring points
   - Scenario probabilities if relevant

Format your response as clear, actionable insights suitable for professional traders and risk managers.
Keep analysis concise but comprehensive - focus on what traders need to know NOW."""

        elif analysis_type == "arbitrage_focus":
            prompt = f"""{base_context}

FOCUS: ARBITRAGE OPPORTUNITY IDENTIFICATION

Analyze this market event specifically for arbitrage opportunities:

1. **DIRECT ARBITRAGE TARGETS**
   - Immediate price dislocations to exploit
   - Related securities or contracts affected
   - Temporal arbitrage windows

2. **RELATIVE VALUE OPPORTUNITIES**
   - Sector rotation possibilities
   - Geographic arbitrage (if applicable)
   - Instrument substitution opportunities

3. **RISK-ADJUSTED RETURNS**
   - Expected return profiles
   - Risk factors and mitigation
   - Holding period expectations

4. **EXECUTION CONSIDERATIONS**
   - Liquidity constraints
   - Timing sensitivity
   - Counterparty considerations

Provide specific, actionable arbitrage ideas with clear entry/exit criteria and risk management."""

        else:  # basic analysis
            prompt = f"""{base_context}

Provide a clear, concise analysis of:
1. What this event means for markets
2. Immediate implications (next 4-8 hours)
3. Key factors to monitor
4. One-sentence summary for traders"""

        return prompt.strip()
    
    def _structure_analysis(self, raw_analysis: str, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Structure the raw analysis into actionable components"""
        
        # Basic structuring - can be enhanced with NLP techniques
        lines = [line.strip() for line in raw_analysis.split('\n') if line.strip()]
        
        return {
            "key_points": lines[:5] if len(lines) >= 5 else lines,
            "full_text": raw_analysis,
            "word_count": len(raw_analysis.split()),
            "has_actionable_content": len([l for l in lines if any(word in l.lower() for word in 
                                   ['recommend', 'suggest', 'consider', 'action', 'buy', 'sell', 'alert'])]),
            "analysis_depth": "comprehensive" if len(raw_analysis) > 200 else "basic"
        }

def test_nim_connection():
    """Test function to verify NIM client works"""
    client = NVIDIANIMClient()
    
    if not client.is_ready():
        print("❌ NIM Client not ready - check API key and connection")
        return False
    
    # Test event
    test_event = {
        'vendor': 'AWS',
        'type': 'S3 Service Disruption',
        'severity': 'CRITICAL',
        'description': 'US-EAST-1 region experiencing widespread S3 service disruption affecting storage operations',
        'confidence': 95.0
    }
    
    print("🧪 Testing NVIDIA NIM connection...")
    result = client.analyze_market_event_deep(test_event, "basic")
    
    if result["status"] == "success":
        print(f"✅ Test successful! Analysis completed in {result['processing_time_ms']:.0f}ms")
        print(f"📝 Preview: {result['raw_analysis'][:100]}...")
        return True
    else:
        print(f"❌ Test failed: {result.get('error', 'Unknown error')}")
        return False

if __name__ == "__main__":
    # Run test if executed directly
    test_nim_connection()
