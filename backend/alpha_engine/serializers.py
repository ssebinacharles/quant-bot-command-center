from rest_framework import serializers
from .models import MarketState, TradeMemory

class MarketStateSerializer(serializers.ModelSerializer):
    class Meta:
        model = MarketState
        fields = '__all__'

class TradeMemorySerializer(serializers.ModelSerializer):
    class Meta:
        model = TradeMemory
        fields = '__all__'