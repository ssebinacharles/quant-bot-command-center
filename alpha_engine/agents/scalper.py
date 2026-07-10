import os
import json
from groq import Groq

class GroqScalperAgent:
    def __init__(self):
        # Fallback to direct env fetch if Django settings aren't fully loaded in standalone tests
        self.api_key = os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("GROQ_API_KEY missing from environment variables.")
        
        self.client = Groq(api_key=self.api_key)
        # Using Llama 3.3 70B for institutional reasoning speeds on Groq LPUs
        self.model = "llama-3.3-70b-versatile" 

    def analyze_market_sequence(self, feature_matrix):
        """
        Sends the sequential feature matrix to Groq and extracts a trading decision.
        """
        system_prompt = (
            "You are an elite high-frequency algorithmic scalping agent executing trades on XAUUSD (Gold).\n"
            "You will be handed a 2D matrix representing a historical timeline of normalized market states "
            "moving from index 0 (oldest bar) to index 9 (most current bar).\n\n"
            "Each row contains 6 normalized indicators bound between -1.0 and 1.0:\n"
            " - [0]: 1-period returns\n"
            " - [1]: 5-period returns\n"
            " - [2]: Normalized Volatility (ATR)\n"
            " - [3]: Distance from 20-period High/Low Midpoint\n"
            " - [4, 5]: Order Flow / Volume Metrics\n\n"
            "CRITICAL: You must reply with a valid JSON object ONLY. Do not write introductory prose or conversational explanations. "
            "The JSON structure must match this exact format:\n"
            "{\n"
            '  "action": "BUY" | "SELL" | "HOLD",\n'
            '  "confidence": <integer percentage between 0 and 100>,\n'
            '  "reason": "<short structural technical justification sentences>"\n'
            "}"
        )

        user_content = f"Analyze this market sequence matrix to determine the immediate execution behavior:\n{json.dumps(feature_matrix)}"

        try:
            # Leverage Groq's native JSON mode to guarantee parsing stability
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                temperature=0.1,  # Low temperature guarantees deterministic calculation alignment
                response_format={"type": "json_object"}
            )
            
            raw_output = response.choices[0].message.content
            return json.loads(raw_output)
            
        except Exception as e:
            # Resilient fallback state in case of connection limits or API hiccups
            return {
                "action": "HOLD",
                "confidence": 0,
                "reason": f"Execution pipeline error: {str(e)}"
            }