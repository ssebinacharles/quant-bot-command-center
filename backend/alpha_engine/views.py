import logging
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
from .services.analytics import PerformanceAnalyticsService
from .services.portfolio import PortfolioManagerService
from .services.layering import GoldLayeringEngine
from .services.probability import ProbabilityEngine

logger = logging.getLogger(__name__)

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
        return Response(serializer.data, status=status.HTTP_200_OK)


# =====================================================================
# 2. THE CENTRAL QUANT CONTROL ROTOR
# =====================================================================

class TradeExecutionView(APIView):
    """
    The Command Router: Receives telemetry data from the MT5/WebSocket bridge,
    saves the market state, processes dynamic AI actions, and manages risk.
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [AllowAny]  # Sandbox testing mode

    def post(self, request):
        telemetry = request.data
        
        # -------------------------------------------------------------
        # Telemetry Parsing & Defensive Type Normalization
        # -------------------------------------------------------------
        symbol = telemetry.get("symbol", "XAUUSD")
        
        try:
            current_price = float(telemetry.get("current_price"))
        except (TypeError, ValueError):
            return Response(
                {"error": "Missing or invalid 'current_price' telemetry parameter."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            account_balance = float(telemetry.get("balance", 10000.00))
            current_equity = float(telemetry.get("equity", account_balance))
            rsi = float(telemetry.get("rsi_14", 50.0))
            atr = float(telemetry.get("atr_14", 1.50))
        except (TypeError, ValueError):
            return Response(
                {"error": "Invalid numerical types supplied in telemetry payload."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        active_positions = telemetry.get("active_positions", [])

        # -------------------------------------------------------------
        # Initialize Service Suite
        # -------------------------------------------------------------
        brain = MarketBrainService()
        risk_manager = RiskManagerService()
        analytics = PerformanceAnalyticsService()
        portfolio_manager = PortfolioManagerService()
        layering_engine = GoldLayeringEngine()
        probability_engine = ProbabilityEngine()

        # =============================================================
        # 1. GLOBAL PORTFOLIO DRAWDOWN GUARD
        # =============================================================
        drawdown_action = portfolio_manager.evaluate_drawdown(
            current_equity=current_equity, 
            account_balance=account_balance
        )
        if drawdown_action == "FLATTEN_ALL":
            logger.warning("[RISK OVERRIDE] Global portfolio drawdown threshold breached.")
            return Response({
                "action": "FLATTEN_ALL",
                "reasoning": "Global portfolio drawdown threshold breached. Emergency stop and flatten active."
            }, status=status.HTTP_200_OK)

        # =============================================================
        # 2. MARKET REGIME DETECTION
        # =============================================================
        regime, risk_multiplier = brain.detect_regime(
            rsi=rsi,
            atr=atr,
            price=current_price
        )
        logger.debug(f"Checking regime - {regime} (Multiplier: {risk_multiplier})")

        # =============================================================
        # 3. SELF-LEARNING VETO LOOP
        # =============================================================
        learning_veto = analytics.evaluate_regime_performance_veto(regime=regime)
        if learning_veto.get("veto") is True or learning_veto.get("action") == "BLOCK":
            return Response({
                "action": "HOLD",
                "reasoning": f"Self-Learning Block: {learning_veto.get('reason', 'Underperforming regime')}"
            }, status=status.HTTP_200_OK) 

        # =============================================================
        # 4. ACTIVE POSITION MANAGEMENT & DYNAMIC EXIT STRATEGY
        # =============================================================
        exit_decision = portfolio_manager.evaluate_active_exits(
            active_positions=active_positions,
            current_price=current_price,
            atr=atr
        )
        if exit_decision.get("action") in ["CLOSE_POSITION", "PARTIAL_CLOSE", "TRAILING_STOP_UPDATE"]:
            return Response(exit_decision, status=status.HTTP_200_OK)

        # =============================================================
        # 5. CONSULT AI DECISION PIPELINE
        # =============================================================
        ai_payload = brain.analyze_market_and_positions(
            market_data={"symbol": symbol, "current_price": current_price, "rsi_14": rsi, "atr_14": atr},
            active_positions=active_positions
        )

        action = ai_payload.get("action", "HOLD")
        confidence = ai_payload.get("confidence_score", 0.0)
        reasoning = ai_payload.get("reasoning", "No thesis provided.")

        if action == "HOLD":
            return Response({"action": "HOLD", "reasoning": reasoning}, status=status.HTTP_200_OK)

        # =============================================================
        # 6. PROBABILITY ENGINE (Mathematical Edge Veto)
        # =============================================================
        baseline_risk_dollars = account_balance * (0.01 * float(risk_multiplier))
        baseline_reward_dollars = baseline_risk_dollars * 3.0

        ev_decision = probability_engine.calculate_regime_ev(
            regime=regime,
            proposed_risk=baseline_risk_dollars,
            proposed_reward=baseline_reward_dollars
        )

        safe_ev = float(ev_decision.get("ev", 0.0) or 0.0)
        is_blocked = (
            ev_decision.get("action") == "BLOCK" or 
            (safe_ev <= 0 and ev_decision.get("reason") != "Gathering data")
        )

        if is_blocked:
            return Response({
                "action": "HOLD",
                "reasoning": f"Math Veto: {ev_decision.get('reason', 'Insufficient EV')} (EV: ${safe_ev:.2f})"
            }, status=status.HTTP_200_OK)

        # =============================================================
        # 7. SMART MULTI-LAYERING EVALUATION (Gold Scalper DNA)
        # =============================================================
        layer_decision = layering_engine.calculate_next_layer(
            active_positions=active_positions,
            current_price=current_price,
            atr=atr,
            signal_action=action
        )

        if layer_decision.get("action") in ["BLOCK_TRADE", "HOLD"]:
            return Response({
                "action": "HOLD", 
                "reasoning": layer_decision.get("reason", "Layering engine hold.")
            }, status=status.HTTP_200_OK)

        # =============================================================
        # 8. POSITION RISK CALCULATOR
        # =============================================================
        adjusted_risk_pct = 0.01 * float(risk_multiplier)
        risk_manager.max_risk_pct = adjusted_risk_pct

        risk_profile = risk_manager.evaluate_and_size_trade(
            account_balance=account_balance,
            entry_price=current_price,
            atr=atr,
            action=action,
            symbol=symbol
        )

        if risk_profile.get("status") == "REJECTED":
            return Response({
                "action": "HOLD", 
                "reasoning": f"Risk engine override: {risk_profile.get('reason')}"
            }, status=status.HTTP_200_OK)

        final_lots = risk_profile.get("lots", 0.01)
        if layer_decision.get("action") == "EXECUTE_LAYER":
            final_lots = layer_decision.get("target_lots", final_lots)

        # =============================================================
        # 9. LOG MARKET STATE & DISPATCH EXECUTION
        # =============================================================
        state_record = MarketState.objects.create(
            symbol=symbol,
            current_price=current_price,
            rsi_14=rsi,
            atr_14=atr,
            market_regime=regime,
            risk_multiplier=risk_multiplier
        )

        execution_payload = {
            "action": action,
            "symbol": symbol,
            "lots": final_lots,
            "stop_loss": risk_profile.get("stop_loss"),
            "take_profit": risk_profile.get("take_profit"),
            "reasoning": f"[Confidence: {confidence}%] [EV: ${safe_ev:.2f}] {reasoning}",
            "market_state_id": state_record.id
        }

        return Response(execution_payload, status=status.HTTP_200_OK)


# =====================================================================
# 3. PERFORMANCE DASHBOARD ENDPOINT
# =====================================================================

class PerformanceDashboardView(APIView):
    """
    Serves compiled performance aggregations and automated AI 
    self-learning optimization recommendations to the UI.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        analytics = PerformanceAnalyticsService()
        metrics = analytics.generate_dashboard_metrics()
        return Response(metrics, status=status.HTTP_200_OK)