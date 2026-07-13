import uuid
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import TradeLog
from .services.brain import MarketBrainService
from .services.risk import RiskManagerService
from rest_framework import viewsets
from rest_framework.decorators import action
from alpha_engine.models import TradeLog, MarketRegime
from alpha_engine.serializers import TradeLogSerializer, MarketRegimeSerializer

class TradeLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Automated API controller providing live streams and replay buffers
    of system trading activity, sorted by the latest execution first.
    """
    # FIX 1: Changed '-timestamp' to '-created_at'
    queryset = TradeLog.objects.all().order_by('-created_at')
    serializer_class = TradeLogSerializer

    @action(detail=False, methods=['get'], url_path='replay-buffer')
    def replay_buffer(self, request):
        """
        Exposes the internal historical window needed for the user dashboard.
        Tries to use your custom manager, falls back to standard slicing if needed.
        """
        if hasattr(TradeLog.objects, 'get_recent_buffer'):
            recent_trades = TradeLog.objects.get_recent_buffer(limit=25)
        else:
            # FIX 2: Changed '-timestamp' to '-created_at' here as well
            recent_trades = TradeLog.objects.all().order_by('-created_at')[:25]
            
        serializer = self.get_serializer(recent_trades, many=True)
        return Response(serializer.data)


class MarketRegimeViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Optional addition: Exposes the current macro market context 
    (Trending, Ranging, High Volatility, etc.) to your React frontend.
    """
    # Keeps your safe fallback check intact
    queryset = MarketRegime.objects.all().order_by('-created_at') if hasattr(MarketRegime, 'created_at') else MarketRegime.objects.all()
    serializer_class = MarketRegimeSerializer

class TradeExecutionView(APIView):
    """
    The Command Router: Receives live MT5 data, consults the AI, 
    calculates risk, and returns exact execution instructions.
    """
    def post(self, request):
        data = request.data
        
        # 1. Extract the minimum required terminal state
        symbol = data.get("symbol", "XAUUSD")
        account_balance = data.get("account_balance")
        current_price = data.get("current_price")
        atr = data.get("atr_14")
        
        if not all([account_balance, current_price, atr]):
            return Response(
                {"error": "Missing required fields: account_balance, current_price, or atr_14"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # 2. Consult the Groq Decision Engine
        brain = MarketBrainService()
        decision = brain.analyze_market_snapshot(data)
        
        # If the AI says hold, we terminate the process immediately.
        if decision.get("action") == "HOLD":
            return Response({
                "status": "HOLD", 
                "reason": decision.get("reason")
            }, status=status.HTTP_200_OK)
        
        # 3. Pass through Risk Management Core
        risk_manager = RiskManagerService()
        risk_profile = risk_manager.evaluate_and_size_trade(
            account_balance=account_balance,
            entry_price=current_price,
            atr=atr,
            action=decision["action"],
            symbol=symbol
        )
        
        if risk_profile.get("status") == "REJECTED":
            return Response({
                "status": "REJECTED_BY_RISK", 
                "reason": risk_profile.get("reason")
            }, status=status.HTTP_200_OK)
        
        # 4. Log the generated signal into the database as PENDING
        # We generate a temporary ticket ID until MT5 confirms the actual broker execution
        temp_ticket = f"PENDING_{uuid.uuid4().hex[:8].upper()}"
        
        trade_log = TradeLog.objects.create(
            ticket_id=temp_ticket,
            symbol=symbol,
            action=risk_profile["action"],
            entry_price=risk_profile["entry_price"],
            lots=risk_profile["lots"],
            ai_confidence_score=decision.get("confidence", 0),
            raw_groq_response=decision,
            feature_snapshot=data
        )
        
        # 5. Return the exact execution blueprint back to MT5
        return Response({
            "status": "EXECUTE",
            "db_id": trade_log.id,
            "action": risk_profile["action"],
            "symbol": risk_profile["symbol"],
            "lots": risk_profile["lots"],
            "stop_loss": risk_profile["stop_loss"],
            "take_profit": risk_profile["take_profit"],
            "reasoning": decision.get("reason")
        }, status=status.HTTP_200_OK)