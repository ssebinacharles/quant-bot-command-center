from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.decorators import action
from alpha_engine.models import TradeLog, MarketRegime
from alpha_engine.serializers import TradeLogSerializer, MarketRegimeSerializer

class TradeLogViewSet(viewsets.ModelViewSet):
    """
    Automated API controller providing live streams and replay buffers
    of system trading activity.
    """
    queryset = TradeLog.objects.all()
    serializer_class = TradeLogSerializer

    @action(detail=False, methods=['get'], url_path='replay-buffer')
    def replay_buffer(self, request):
        """Exposes the internal historical window needed for the user dashboard."""
        recent_trades = TradeLog.objects.get_recent_buffer(limit=25)
        serializer = self.get_serializer(recent_trades, many=True)
        return Response(serializer.data)