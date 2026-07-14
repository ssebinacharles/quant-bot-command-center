import os
import json
from groq import Groq

class MarketBrainService:
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")
        if not self.api_key:
            # Fallback for local sandbox testing if env var isn't set yet
            self.api_key = "dummy_key_for_testing"
        self.client = Groq(api_key=self.api_key)

    # =====================================================================
    # 1. MARKET REGIME DETECTOR
    # =====================================================================
    def detect_regime(self, rsi, atr, price):
        """
        Calculates the current structural market phase based on key technical features.
        Returns: (regime_string, risk_multiplier)
        """
        # Safe type conversion
        try:
            rsi = float(rsi) if rsi is not None else 50.0
            atr = float(atr) if atr is not None else 1.0
        except ValueError:
            rsi, atr = 50.0, 1.0

        # Heuristic-based classification (Can be expanded with ML/clustering later)
        if rsi >= 75.0:
            return "BULL_CLIMAX", 0.50  # Reduce risk, market is highly overextended
        elif rsi <= 25.0:
            return "BEAR_CLIMAX", 0.50  # Reduce risk, oversold exhaustion
        elif 45.0 <= rsi <= 55.0 and atr < 1.5:
            return "RANGING", 1.00      # Normal range-bound trading
        elif rsi > 55.0:
            return "TRENDING_UP", 1.25  # High-confidence trend alignment; scale up slightly
        elif rsi < 45.0:
            return "TRENDING_DOWN", 1.25
        
        return "UNKNOWN", 1.00

    # =====================================================================
    # 2. DYNAMIC AI EXIT ENGINE
    # =====================================================================
    def evaluate_active_exits(self, active_positions, rsi, regime):
        """
        Scans all currently open MT5 trades and decides if we need to 
        manually cut losses or bank profits before hitting hard SL/TP.
        """
        try:
            rsi = float(rsi)
        except (ValueError, TypeError):
            rsi = 50.0

        for pos in active_positions:
            ticket = pos.get("ticket")
            pos_type = pos.get("type")
            profit = float(pos.get("profit", 0))

            # Dynamic Take Profit (Exiting when indicators are exhausted)
            if pos_type == "SELL" and rsi <= 30.0 and profit > 0:
                return {
                    "status": "close_request",
                    "action": "CLOSE",
                    "ticket": ticket,
                    "reasoning": f"RSI is heavily oversold ({rsi}). Taking early manual profit of ${profit} before key support bounce."
                }
            if pos_type == "BUY" and rsi >= 70.0 and profit > 0:
                return {
                    "status": "close_request",
                    "action": "CLOSE",
                    "ticket": ticket,
                    "reasoning": f"RSI is heavily overbought ({rsi}). Taking early manual profit of ${profit} before resistance rejection."
                }

            # Dynamic Emergency Exit (Cutting losses if regime shifts violently)
            if pos_type == "BUY" and regime == "BEAR_CLIMAX" and profit < -10.0:
                return {
                    "status": "close_request",
                    "action": "CLOSE",
                    "ticket": ticket,
                    "reasoning": f"Market shifted into BEAR_CLIMAX. Dynamically cutting buy trade at ${profit} to protect capital."
                }
            if pos_type == "SELL" and regime == "BULL_CLIMAX" and profit < -10.0:
                return {
                    "status": "close_request",
                    "action": "CLOSE",
                    "ticket": ticket,
                    "reasoning": f"Market shifted into BULL_CLIMAX. Dynamically cutting sell trade at ${profit} to protect capital."
                }

        return None

    # =====================================================================
    # 3. QUANT DECISION PIPELINE & CONFIDENCE ENGINE
    # =====================================================================
    def analyze_market_and_positions(self, market_data, active_positions):
        """
        Combines regime detection, active trade inspection, and 
        generative LLM analysis to determine exact trade signals.
        """
        rsi = market_data.get("rsi_14", 50.0)
        atr = market_data.get("atr_14", 1.50)
        current_price = market_data.get("current_price")
        symbol = market_data.get("symbol", "XAUUSD")

        # Step 1: Detect Market Regime & Scale Risks
        regime, risk_multiplier = self.detect_regime(rsi, atr, current_price)
        market_data["market_regime"] = regime  # Cache back into the data payload
        
        print(f"📊 Regime Detected: {regime} (Risk Multiplier: {risk_multiplier})")

        # Step 2: Evaluate Dynamic Exits for Open Positions
        exit_signal = self.evaluate_active_exits(active_positions, rsi, regime)
        if exit_signal:
            return exit_signal

        # Step 3: Layering Check (Limit total risk)
        if len(active_positions) >= 3:
            return {
                "status": "HOLD",
                "action": "HOLD",
                "reasoning": f"Layering capacity reached ({len(active_positions)} active trades). Halting scale-ins."
            }

        # Step 4: Fallback for Sandbox/Development without API Keys
        if self.api_key == "dummy_key_for_testing":
            return self._generate_fallback_signal(regime, rsi, current_price, symbol)

        # Step 5: Consult Groq with Quant Parameters
        prompt = f"""
        You are the Core Decision Matrix for a Quantum Scalping Bot trading {symbol}.
        Analyze the following live telemetry snapshot:
        - Current Price: {current_price}
        - RSI (14): {rsi}
        - ATR (14): {atr}
        - Detected Regime: {regime}
        - Open Positions: {len(active_positions)}/3

        Your objective is high-probability, short-term scalping with minimal risk hits. 
        Determine if we should execute a BUY, SELL, or stand by with a HOLD.
        
        Respond ONLY in a strict JSON block matching this structure:
        {{
            "action": "BUY" or "SELL" or "HOLD",
            "confidence_score": integer between 0 and 100,
            "reasoning": "A concise, technical, 1-sentence trade thesis."
        }}
        """

        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a cold-headed, high-performance quantitative trade risk controller. You output raw JSON only."
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                model="mixtral-8x7b-32768", # Ultra-fast model for latency-sensitive trade loops
                temperature=0.1, # Keep logic deterministic
                response_format={"type": "json_object"}
            )
            
            raw_response = chat_completion.choices[0].message.content
            parsed = json.loads(raw_response)
            
            # Extract and inject execution metadata
            action = parsed.get("action", "HOLD").upper()
            confidence = float(parsed.get("confidence_score", 0))
            reasoning = parsed.get("reasoning", "No thesis provided.")

            # Filter signals through the Confidence Engine threshold
            if action != "HOLD" and confidence >= 70.0:
                return {
                    "status": "executed",
                    "action": action,
                    "confidence_score": confidence,
                    "reasoning": f"[Regime: {regime}] {reasoning}",
                    "lots": 0.01  # Basic lot size (will scale in further updates)
                }
            
            return {
                "status": "HOLD",
                "action": "HOLD",
                "reasoning": f"Signal rejected. Action: {action} | Confidence Score: {confidence}% (Required: 70%)"
            }

        except Exception as e:
            print(f"⚠️ Groq API failed, using local fallback execution. Error: {e}")
            return self._generate_fallback_signal(regime, rsi, current_price, symbol)

    def _generate_fallback_signal(self, regime, rsi, price, symbol):
        """Deterministic safety algorithm if the LLM API experiences latency/outages."""
        try:
            rsi = float(rsi)
            price = float(price)
        except:
            return {"status": "HOLD", "action": "HOLD", "reasoning": "Fallback parsing error."}

        if regime == "TRENDING_DOWN" and rsi > 65.0:
            return {
                "status": "executed",
                "action": "SELL",
                "confidence_score": 85.0,
                "reasoning": f"Local Fallback: Scalping short alignment on oversold correction in {regime}.",
                "lots": 0.01
            }
        elif regime == "TRENDING_UP" and rsi < 35.0:
            return {
                "status": "executed",
                "action": "BUY",
                "confidence_score": 85.0,
                "reasoning": f"Local Fallback: Scalping long alignment on pullback in {regime}.",
                "lots": 0.01
            }
            
        return {
            "status": "HOLD",
            "action": "HOLD",
            "reasoning": f"Local Fallback: Standing by in {regime} (RSI: {rsi}). No edge detected."
        }