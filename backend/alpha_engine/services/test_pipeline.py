from alpha_engine.services.brain import MarketBrainService

def run_mock_execution_cycle():
    # 1. Gather technical data (This will come from your streaming engine later)
    mock_market_metrics = {
        "ticker": "XAUUSD",
        "timeframe": "M5",
        "current_price": 2345.50,
        "rsi_14": 74.2,              # Overbought conditions
        "atr_14": 2.10,              # Volatility reading
        "macd_line": 0.45,
        "signal_line": 0.55,         # Bearish crossover signature
        "market_regime": "RANGING_HIGH"
    }
    
    print("🧠 Spawning Market Brain Service Instance...")
    brain = MarketBrainService()
    
    print("📡 Passing live matrix snapshot to Groq Engine...")
    decision = brain.analyze_market_snapshot(mock_market_metrics)
    
    print("\n⚡ [DECISION RECOVERED]")
    print(f"Action Flag: {decision.get('action')}")
    print(f"Confidence Level: {decision.get('confidence')}%")
    print(f"Engine Log: {decision.get('reason')}")

if __name__ == "__main__":
    run_mock_execution_cycle()