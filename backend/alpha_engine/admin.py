from django.contrib import admin
from .models import MarketState, TradeMemory

@admin.register(MarketState)
class MarketStateAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'symbol', 'current_price', 'rsi_14', 'market_regime', 'risk_multiplier')
    list_filter = ('market_regime', 'symbol')
    search_fields = ('symbol', 'market_regime')
    ordering = ('-timestamp',)

@admin.register(TradeMemory)
class TradeMemoryAdmin(admin.ModelAdmin):
    list_display = ('ticket_id', 'symbol', 'action', 'status', 'lots', 'entry_price', 'profit', 'opened_at')
    list_filter = ('status', 'action', 'symbol')
    search_fields = ('ticket_id', 'symbol', 'action')
    ordering = ('-opened_at',)