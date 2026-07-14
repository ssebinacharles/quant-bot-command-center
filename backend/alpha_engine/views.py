import uuid
from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.authentication import TokenAuthentication

from .models import MarketState, TradeMemory
from .serializers import MarketStateSerializer, TradeMemorySerializer
from .services.brain import MarketBrainService
from .services.risk import RiskManagerService

# =====================================================================
# 1. VIEWSETS FOR THE REACT FRONTEND
# =====================================================================

class MarketStateViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Exposes technical snapshots and macro-regime classifications 
    to your React frontend dashboard, sorted by the latest data first.
    """
    queryset = MarketState.objects.all().order_by('-timestamp')
    serializer_class = MarketStateSerializer


class TradeMemoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Exposes live trading logs to your React frontend, featuring an 
    MQL5-style replay-buffer for real-time visualization.
    """
    queryset = TradeMemory.objects.all().order_by('-opened_at')
    serializer_class = TradeMemorySerializer

    @action(detail=False, methods=['get'], url_path='replay-buffer')
    def replay_buffer(self, request):
        """
        Emulates the MQL5 replayBuffer array. Instantly queries 
        the database for the last 25 closed trades for analysis.
        """
        if hasattr(TradeMemory.objects, 'get_recent_buffer'):
            recent_trades = TradeMemory.objects.get_recent_buffer(limit=25)
        else:
            recent_trades = TradeMemory.objects.all().order_by('-opened_at')[:25]
            
        serializer = self.get_serializer(recent_trades, many=True)
        return Response(serializer.data)


# =====================================================================
# 2. THE CENTRAL QUANT CONTROL ROTOR
# =====================================================================

class TradeExecutionView(APIView):
    """
    The Command Router: Receives telemetry data from the MT5 bridge,
    saves the market state, processes dynamic AI actions, and manages risk.
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [AllowAny]  # Keep as AllowAny for rapid sandbox testing!
    
    def post(self, request):
        print("🔑 INCOMING TELEMETRY RECEIVED. AUTH:", request.headers.get('Authorization'))
        data = request.data
        
        # 1. Extract core data points
        symbol = data.get("symbol", "XAUUSD")
        account_balance = data.get("account_balance")
        current_price = data.get("current_price")
        atr = data.get("atr_14")
        rsi = data.get("rsi_14")
        market_regime = data.get("market_regime", "UNKNOWN")
        active_positions = data.get("active_positions", [])
        
        if not all([account_balance, current_price, atr]):
            return Response(
                {"error": "Missing required fields: account_balance, current_price, or atr_14"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # 2. Log exact conditions in the database (Feature Engine Cache)
        state = MarketState.objects.create(
            symbol=symbol,
            current_price=current_price,
            rsi_14=rsi,
            atr_14=atr,
            market_regime=market_regime
        )
        
        # 3. Call the Market Brain
        brain = MarketBrainService()
        if hasattr(brain, 'analyze_market_and_positions'):
            decision = brain.analyze_market_and_positions(data, active_positions)
        else:
            decision = brain.analyze_market_snapshot(data)
        
        # 4. Handle HOLDS & DYNAMIC CLOSURES
        action_type = decision.get("action")
        
        if action_type == "HOLD":
            return Response({
                "status": "HOLD", 
                "reason": decision.get("reason", decision.get("reasoning", "System standing by."))
            }, status=status.HTTP_200_OK)
            
        if decision.get("status") == "close_request":
            # Dynamic Exit requested! Command the bridge to execute a close sequence
            return Response(decision, status=status.HTTP_200_OK)
        
        # 5. Evaluate and size new trades through your Risk Manager
        risk_manager = RiskManagerService()
        risk_profile = risk_manager.evaluate_and_size_trade(
            account_balance=account_balance,
            entry_price=current_price,
            atr=atr,
            action=action_type,
            symbol=symbol
        )
        
        if risk_profile.get("status") == "REJECTED":
            return Response({
                "status": "REJECTED_BY_RISK", 
                "reason": risk_profile.get("reason")
            }, status=status.HTTP_200_OK)
        
        # 6. Save trade with uuid mapping inside TradeMemory
        temp_ticket = f"PENDING_{uuid.uuid4().hex[:8].upper()}"
        
        trade_log = TradeMemory.objects.create(
            market_state=state,
            ticket_id=temp_ticket,
            symbol=symbol,
            action=risk_profile["action"],
            status='PENDING',
            lots=risk_profile["lots"],
            entry_price=risk_profile["entry_price"],
            stop_loss=risk_profile.get("stop_loss"),
            take_profit=risk_profile.get("take_profit"),
            ai_confidence_score=decision.get("confidence", decision.get("confidence_score", 0)),
            ai_reasoning=decision.get("reason", decision.get("reasoning", "Execution authorized.")),
            raw_groq_response=decision,
            feature_snapshot=data
        )
        
        # 7. Package complete blueprint payload for MT5 execution
        return Response({
            "status": "executed",
            "db_id": trade_log.id,
            "action": risk_profile["action"],
            "symbol": risk_profile["symbol"],
            "lots": risk_profile["lots"],
            "stop_loss": risk_profile["stop_loss"],
            "take_profit": risk_profile["take_profit"],
            "reasoning": decision.get("reason", decision.get("reasoning", ""))
        }, status=status.HTTP_200_OK)