from django.db import models
from django.utils import timezone

# =====================================================================
# 1. THE FEATURE ENGINE & REGIME DETECTOR (Unified Market State)
# =====================================================================

class MarketState(models.Model):
    """
    Captures the exact technical and structural state of the market
    at the moment a decision is requested or regime is classified.
    """
    REGIME_CHOICES = [
        ('TRENDING_UP', 'Trending Up'),
        ('TRENDING_DOWN', 'Trending Down'),
        ('RANGING', 'Ranging/Bound'),
        ('HIGH_VOLATILITY', 'High Volatility/Choppy'),
        ('BULL_CLIMAX', 'Bullish Climax'),
        ('BEAR_CLIMAX', 'Bearish Climax'),
        ('UNKNOWN', 'Unknown'),
    ]

    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    symbol = models.CharField(max_length=20, default='XAUUSD')
    current_price = models.DecimalField(max_digits=10, decimal_places=5)
    
    # Technical Indicators (The Feature Engine)
    rsi_14 = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    atr_14 = models.DecimalField(max_digits=10, decimal_places=5, null=True, blank=True)
    
    # AI Classification
    market_regime = models.CharField(max_length=20, choices=REGIME_CHOICES, default='UNKNOWN')
    gpt_regime_classification = models.TextField(help_text="Raw reasoning from the AI engine", null=True, blank=True)
    risk_multiplier = models.DecimalField(max_digits=4, decimal_places=2, default=1.00)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.symbol} @ {self.current_price} | Regime: {self.market_regime}"


# =====================================================================
# 2. THE QUANT PORTFOLIO LEDGER (Unified Trade Memory)
# =====================================================================

class TradeMemoryQuerySet(models.QuerySet):
    def get_recent_buffer(self, limit=50):
        """Emulates the MQL5 replayBuffer array for tracking recent performance."""
        return self.filter(status='CLOSED').order_by('-closed_at')[:limit]


class TradeMemoryManager(models.Manager):
    def get_queryset(self):
        return TradeMemoryQuerySet(self.model, using=self._db)
        
    def get_recent_buffer(self, limit=50):
        return self.get_queryset().get_recent_buffer(limit)


class TradeMemory(models.Model):
    """
    The Trade Ledger: Logs every AI decision, execution, and final outcome.
    Links directly to MarketState for back-analysis and self-learning.
    """
    ACTION_CHOICES = [
        ('BUY', 'Buy'),
        ('SELL', 'Sell'),
        ('HOLD', 'Hold'),
        ('CLOSE', 'Close')
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('OPEN', 'Open'),
        ('CLOSED', 'Closed'),
        ('CANCELLED', 'Cancelled'),
        ('FAILED', 'Failed execution')
    ]

    # Structural link to the market conditions that triggered this trade
    market_state = models.ForeignKey(MarketState, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Execution metrics
    ticket_id = models.CharField(max_length=50, unique=True, null=True, blank=True, help_text="MT5 Deal/Order Ticket ID")
    symbol = models.CharField(max_length=20, default='XAUUSD')
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='PENDING', db_index=True)
    lots = models.DecimalField(max_digits=6, decimal_places=2)
    
    # Pricing levels
    entry_price = models.DecimalField(max_digits=10, decimal_places=5)
    exit_price = models.DecimalField(max_digits=10, decimal_places=5, null=True, blank=True)
    stop_loss = models.DecimalField(max_digits=10, decimal_places=5, null=True, blank=True)
    take_profit = models.DecimalField(max_digits=10, decimal_places=5, null=True, blank=True)
    profit = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    # AI Feature Cache & Decision Memory
    ai_confidence_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="Groq Scalper confidence %")
    ai_reasoning = models.TextField(help_text="Decisions details and execution thesis")
    raw_groq_response = models.JSONField(null=True, blank=True, help_text="Complete JSON response block from the Groq LLM")
    feature_snapshot = models.JSONField(null=True, blank=True, help_text="The normalized data matrix sent to Groq")
    
    # Time metadata
    opened_at = models.DateTimeField(default=timezone.now, db_index=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    objects = TradeMemoryManager()

    class Meta:
        ordering = ['-opened_at']

    def __str__(self):
        return f"Ticket {self.ticket_id or 'PENDING'} | {self.action} {self.symbol} | {self.status}"