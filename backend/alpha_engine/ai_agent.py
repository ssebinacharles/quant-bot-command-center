import os
import requests
import json

class GroqTradingAgent:
    def __init__(self):
        # Pulls your Groq API Key from your .env file
        self.api_key = os.getenv("GROQ_API_KEY")
        self.api_url = "https://api.groq.com/openai/v1/chat/completions"

    def analyze_market(self, market_data):
        # Fallback mock decision if no API key is set yet so your code doesn't crash
        if not self.api_key:
            return {
                "action": "BUY" if market_data["trend"] == "UPWARD" else "SELL",
                "confidence": 75,
                "reason": f"Simulated local execution. Micro-trend is {market_data['trend']}."
            }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # Systemic prompt ensuring the AI acts purely as a mechanical scalper
        prompt = f"""
        You are an elite high-frequency algorithmic scalping bot tracking {market_data['symbol']}.
        Current Market State:
        - Bid Price: ${market_data['bid']}
        - Ask Price: ${market_data['ask']}
        - 10-Period SMA: ${market_data['sma_10']}
        - Current Micro-Trend: {market_data['trend']}

        Analyze the data and issue a trade decision. You must respond ONLY with a raw JSON object matching this schema:
        {{
            "action": "BUY" or "SELL" or "HOLD",
            "confidence": integer between 0 and 100,
            "reason": "One sentence technical justification"
        }}
        """

        data = {
            "model": "llama3-70b-8192",  # Fast and competent for structured JSON
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
            "temperature": 0.2
        }

        try:
            response = requests.post(self.api_url, json=data, headers=headers)
            result = response.json()
            # Parse out the inner JSON text from the model response
            return json.loads(result['choices'][0]['message']['content'])
        except Exception as e:
            print(f"Groq API Error: {e}")
            return {"action": "HOLD", "confidence": 0, "reason": "AI connection error."}