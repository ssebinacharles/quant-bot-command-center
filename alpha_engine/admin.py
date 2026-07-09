# backend/alpha_engine/admin.py
from django.contrib import admin
from .models import TradeLog, MarketRegime

@admin.register(TradeLog)
class TradeLogAdmin(admin.ModelAdmin):
    list_display = ('ticket_id', 'symbol', 'action', 'status', 'lots', 'profit', 'ai_confidence_score', 'created_at')
    list_filter = ('status', 'action', 'symbol')
    search_fields = ('ticket_id', 'raw_groq_response')

@admin.register(MarketRegime)
class MarketRegimeAdmin(admin.ModelAdmin):
    list_display = ('symbol', 'current_regime', 'risk_multiplier', 'timestamp')
    list_filter = ('current_regime', 'symbol')