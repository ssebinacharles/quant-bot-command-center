import requests
import json

# URL targeting your new custom execution view
URL = "http://localhost:8000/engine/execute/"

# Simulating a live, highly volatile market snapshot for Gold (XAUUSD)
# This mimics what your local MetaTrader script will transmit
mock_payload = {
    "symbol": "XAUUSD",
    "account_balance": 1000.00,  # A standard $1,000 demo balance
    "current_price": 2345.50,    # Entry price
    "atr_14": 2.50,              # 14-period Average True Range (Volatility)
    "rsi_14": 78.5,              # Overbought condition
    "market_regime": "BULL_CLIMAX"
}

print("🚀 Firing mock market matrix snapshot to Django engine...")

try:
    response = requests.post(URL, json=mock_payload)
    print(f"📡 Server Response Status: {response.status_code}")
    print("\n📦 Returned JSON Payload:")
    print(json.dumps(response.json(), indent=4))
except Exception as e:
    print(f"❌ Connection failed: {str(e)}")