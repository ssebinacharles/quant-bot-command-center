from django.db import models

class MarketRegime(models.Model):
    REGIME_CHOICES = [
        ('TRENDING_UP', 'Trending Up'),
        ('TRENDING_DOWN', 'Trending Down'),
        ('RANGING', 'Ranging/Bound'),
        ('HIGH_VOLATILITY', 'High Volatility/Choppy'),
    ]

    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    symbol = models.CharField(max_length=20, default='XAUUSD')
    current_regime = models.CharField(max_length=20, choices=REGIME_CHOICES)
    gpt_regime_classification = models.TextField(help_text="Raw reasoning from GPT-5.5")
    risk_multiplier = models.DecimalField(max_digits=4, decimal_places=2, default=1.00)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.symbol} - {self.current_regime} @ {self.timestamp.strftime('%Y-%m-%d %H:%M')}"


class TradeLogQuerySet(models.QuerySet):
    def get_recent_buffer(self, limit=50):
        """Emulates the MQL5 replayBuffer array for tracking recent performance."""
        return self.filter(status='CLOSED').order_by()[:limit]

class TradeLogManager(models.Manager):
    def get_queryset(self):
        return TradeLogQuerySet(self.model, using=self._db)
        
    def get_recent_buffer(self, limit=50):
        return self.get_queryset().get_recent_buffer(limit)


class TradeLog(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('OPEN', 'Open'),
        ('CLOSED', 'Closed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    ACTION_CHOICES = [
        ('BUY', 'Buy'),
        ('SELL', 'Sell'),
    ]

    # Structural fields
    ticket_id = models.CharField(max_length=50, unique=True, help_text="MT5 Deal/Order Ticket ID")
    symbol = models.CharField(max_length=20, default='XAUUSD')
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING', db_index=True)
    
    # Execution metrics
    lots = models.DecimalField(max_digits=6, decimal_places=2)
    entry_price = models.DecimalField(max_digits=10, decimal_places=5)
    exit_price = models.DecimalField(max_digits=10, decimal_places=5, null=True, blank=True)
    profit = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    # AI Feature Cache & Context Engine
    ai_confidence_score = models.DecimalField(max_digits=5, decimal_places=2, help_text="Groq Scalper confidence %")
    raw_groq_response = models.JSONField(help_text="Complete JSON response block from the Groq LLM")
    feature_snapshot = models.JSONField(help_text="The normalized data matrix sent to Groq (ATR, Close arrays, etc.)")
    
    # Time metadata
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    objects = TradeLogManager()

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Ticket {self.ticket_id} | {self.action} {self.symbol} | {self.status}"