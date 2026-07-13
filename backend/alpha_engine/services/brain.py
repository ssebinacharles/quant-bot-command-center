import os
import json
import logging
from groq import Groq

logger = logging.getLogger(__name__)

class MarketBrainService:
    """
    The Decision Engine Abstraction Layer.
    Handles communication with high-frequency inference providers.
    """
    def __init__(self):
        # Grab the API key from the environment setup
        self.api_key = os.getenv("GROQ_API_KEY")
        if not self.api_key:
            logger.error("GROQ_API_KEY is missing from environment variables.")
            raise ValueError("GROQ_API_KEY environment variable is not set.")
        
        # Initialize Groq Client
        self.client = Groq(api_key=self.api_key)
        
        # Using a fast, high-context model optimized for speed
        self.model_name = "llama-3.3-70b-versatile"

    def analyze_market_snapshot(self, context_data: dict) -> dict:
        """
        Takes raw technical indicators/regime matrices and determines an execution vector.
        Guaranteed to return a structured dictionary: {"action": ..., "confidence": ..., "reason": ...}
        """
        system_prompt = (
            "You are an elite, risk-averse algorithmic quantum scalper bot backend. "
            "Analyze the given market metrics snapshot and select the highest probability action. "
            "You must return your output strictly as a JSON object matching this exact schema:\n"
            "{\n"
            '  "action": "BUY" | "SELL" | "HOLD",\n'
            '  "confidence": integer between 0 and 100,\n'
            '  "reason": "A highly precise 1-sentence technical justification highlighting indicator convergence."\n'
            "}"
        )
        
        user_prompt = f"Current Technical Array Snapshot:\n{json.dumps(context_data, indent=2)}"
        
        try:
            # Requesting the chat completion with structural enforcement
            completion = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,  # Keep the model ultra-deterministic and analytical
                response_format={"type": "json_object"}  # Hard structural guardrail
            )
            
            raw_response = completion.choices[0].message.content
            parsed_decision = json.loads(raw_response)
            
            # Basic defensive parsing assertions
            if parsed_decision.get("action") not in ["BUY", "SELL", "HOLD"]:
                parsed_decision["action"] = "HOLD"
                
            return parsed_decision

        except Exception as e:
            logger.error(f"Execution Brain critical failure: {str(e)}")
            # Fail-safe guard: If the API blinks, we protect our capital by doing absolutely nothing.
            return {
                "action": "HOLD",
                "confidence": 0,
                "reason": f"Emergency fail-safe triggered. Inference network error: {str(e)}"
            }