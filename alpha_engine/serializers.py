from rest_framework import serializers
from alpha_engine.models import TradeLog, MarketRegime

class TradeLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = TradeLog
        fields = '__all__'

class MarketRegimeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MarketRegime
        fields = '__all__'