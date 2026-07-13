from rest_framework import serializers
from alpha_engine.models import TradeLog, MarketRegime  # Added MarketRegime here

class TradeLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = TradeLog
        fields = [
            'id', 
            'ticket_id', 
            'symbol', 
            'action', 
            'entry_price', 
            'lots', 
            'ai_confidence_score', 
            'raw_groq_response', 
            'feature_snapshot', 
            'created_at'
        ]

# ADD THIS CLASS TO FIX THE IMPORT ERROR:
class MarketRegimeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MarketRegime
        fields = '__all__'  # Automatically serializes all fields inside your MarketRegime model