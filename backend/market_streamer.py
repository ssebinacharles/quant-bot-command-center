import asyncio
import json
import websockets
import aiohttp

# Adjust this URL if your route is configured differently in alpha_engine/urls.py
DJANGO_URL = "http://127.0.0.1:8000/engine/execute/" 

def calculate_simple_rsi(prices, period=14):
    """Calculates a quick rolling RSI over the price buffer."""
    if len(prices) < period + 1:
        return 50.0
    
    gains, losses = [], []
    recent_prices = prices[-(period + 1):]
    
    for i in range(1, len(recent_prices)):
        change = recent_prices[i] - recent_prices[i - 1]
        if change >= 0:
            gains.append(change)
        else:
            losses.append(abs(change))
            
    avg_gain = sum(gains) / period if gains else 0.0
    avg_loss = sum(losses) / period if losses else 1e-9
    
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)

class MarketStreamer:
    def __init__(self, symbol="btcusdt", django_url=DJANGO_URL):
        self.stream_url = f"wss://stream.binance.com:9443/ws/{symbol}@aggTrade"
        self.django_url = django_url
        self.price_buffer = []
        self.symbol = symbol.upper()

    async def send_telemetry(self, session, price, rsi):
        """Sends an async POST request to Django's Alpha Engine."""
        payload = {
            "symbol": self.symbol,
            "current_price": price,
            "equity": 10000.00,
            "balance": 10000.00,
            "rsi_14": rsi,
            "atr_14": 1.50,
            "active_positions": []
        }
        try:
            async with session.post(self.django_url, json=payload, timeout=2) as response:
                res_data = await response.json()
                action = res_data.get("action", "PROCESSED")
                reason = res_data.get("reasoning", res_data.get("reason", "OK"))
                print(f"[⇄ Django Response] HTTP {response.status} | Action: {action} | Detail: {reason}")
        except Exception as e:
            print(f"[!] Failed to connect to Django: {e}")

    async def connect_and_listen(self):
        print(f"[*] Connecting to WebSocket: {self.stream_url}")
        
        async with aiohttp.ClientSession() as session:
            async for websocket in websockets.connect(self.stream_url):
                try:
                    print("[*] Connected! Listening and forwarding telemetry to Django...")
                    tick_count = 0
                    
                    while True:
                        message = await websocket.recv()
                        data = json.loads(message)
                        price = float(data['p'])
                        
                        self.price_buffer.append(price)
                        if len(self.price_buffer) > 100:
                            self.price_buffer.pop(0)

                        tick_count += 1
                        # Fire a telemetry payload to Django every 20 ticks (~every 1-2 seconds)
                        if tick_count % 20 == 0:
                            rsi = calculate_simple_rsi(self.price_buffer)
                            print(f"\n[★ Telemetry Trigger] Price: {price} | RSI: {rsi}")
                            await self.send_telemetry(session, price, rsi)

                except websockets.ConnectionClosed:
                    print("[!] Connection lost. Reconnecting...")
                    await asyncio.sleep(1)
                except Exception as e:
                    print(f"[!] Error: {e}")
                    await asyncio.sleep(5)

if __name__ == "__main__":
    streamer = MarketStreamer(symbol="btcusdt")
    try:
        asyncio.run(streamer.connect_and_listen())
    except KeyboardInterrupt:
        print("\n[*] Shutting down streamer.")
