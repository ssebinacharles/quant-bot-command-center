from django.db import models

class MarketRegime(models.Model):
    """Tracks the state of the market to determine if scalping is safe."""
    timestamp = models.DateTimeField(auto_now_add=True)
    asset = models.CharField(max_length=10) # e.g., XAUUSD
    volatility_index = models.FloatField()
    trend_state = models.CharField(max_length=50) # e.g., "Trending Bullish", "Choppy"
    ai_confidence_score = models.FloatField()

class TradeLog(models.Model):
    """The core evaluation table for the AI feedback loop."""
    ticket_id = models.IntegerField(unique=True)
    asset = models.CharField(max_length=10)
    order_type = models.CharField(max_length=10) # BUY or SELL
    entry_price = models.FloatField()
    exit_price = models.FloatField(null=True, blank=True)
    pnl = models.FloatField(null=True, blank=True)
    
    # AI Memory Context
    regime_context = models.ForeignKey(MarketRegime, on_delete=models.SET_NULL, null=True)
    ai_reasoning = models.TextField() # Store the LLM's logic for taking the trade
    was_successful = models.BooleanField(default=False)