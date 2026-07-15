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
import logging

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
        telemetry = request.data
        
        symbol = telemetry.get("symbol", "XAUUSD")
        current_price = telemetry.get("current_price")
        current_equity = telemetry.get("equity", telemetry.get("balance", 10000.00))
        account_balance = telemetry.get("balance", 10000.00)
        rsi = telemetry.get("rsi_14", 50.0)
        atr = telemetry.get("atr_14", 1.50)
        active_positions = telemetry.get("active_positions", [])

        if not current_price:
            return Response({"error": "Missing current_price telemetry."}, status=status.HTTP_400_BAD_REQUEST)

        # Initialize Services
        brain = MarketBrainService()
        risk_manager = RiskManagerService()
        analytics = PerformanceAnalyticsService()
        portfolio_manager = PortfolioManagerService()
        layering_engine = GoldLayeringEngine()
        probability_engine = ProbabilityEngine() # <--- NEW: Initialize the EV Engine

        # ==========================================
        # 1. GLOBAL PORTFOLIO DRAWDOWN GUARD
        # ==========================================
        # Stops trading or flattens positions if cumulative drawdown breaches safety thresholds
        drawdown_action = portfolio_manager.evaluate_drawdown(
            current_equity=current_equity, 
            account_balance=account_balance
        )
        if drawdown_action == "FLATTEN_ALL":
            return Response({
                "action": "FLATTEN_ALL",
                "reasoning": "Global portfolio drawdown threshold breached. Emergency stop and flatten active."
            }, status=status.HTTP_200_OK)
        # ==========================================
        # 2. MARKET REGIME DETECTION
        # ==========================================
        # Classifies the market state (e.g., TRENDING_UP, TRENDING_DOWN, RANGING) 
        # and returns a risk multiplier to scale trade size dynamically.
        regime_data = brain.detect_regime(
            rsi=rsi,
            atr=atr,
            price=current_price,                         
        )
        print(f"DEBUG: Checking regime - {regime}")
        learning_veto = analytics.evaluate_regime_performance_veto(regime=regime)

        # ==========================================
        # 3. SELF-LEARNING VETO LOOP
        # ==========================================
        # Inspects past database trade records. If recent win rates in the current 
        # regime fall below a safety threshold, it halts further exposure in this environment.
        learning_veto = analytics.evaluate_regime_performance_veto(regime=regime)
        if learning_veto.get("veto", False):
            return Response({
                "action": "HOLD",
                "reasoning": f"Self-Learning Veto: {learning_veto.get('reason', 'Underperforming regime characteristics detected.')}"
            }, status=status.HTTP_200_OK)

        # ==========================================
        # 4. ACTIVE POSITION MANAGEMENT & DYNAMIC EXIT STRATEGY
        # ==========================================
        # Manages live open trades—calculates trailing stops, checks partial profit-taking, 
        # and signals exits to MT5 if key risk parameters or trend-reversal milestones are met.
        exit_decision = portfolio_manager.evaluate_active_exits(
            active_positions=active_positions,
            current_price=current_price,
            atr=atr
        )
        if exit_decision.get("action") in ["CLOSE_POSITION", "PARTIAL_CLOSE", "TRAILING_STOP_UPDATE"]:
            return Response(exit_decision, status=status.HTTP_200_OK)

        # ==========================================
        # 5. CONSULT AI DECISION PIPELINE
        # ==========================================
        ai_payload = brain.analyze_market_and_positions(
            market_data={"symbol": symbol, "current_price": current_price, "rsi_14": rsi, "atr_14": atr},
            active_positions=active_positions
        )

        action = ai_payload.get("action", "HOLD")
        confidence = ai_payload.get("confidence_score", 0.0)
        reasoning = ai_payload.get("reasoning", "No thesis provided.")

        if action == "HOLD":
            return Response({"action": "HOLD", "reasoning": reasoning}, status=status.HTTP_200_OK)

        # ==========================================
        # 6. PROBABILITY ENGINE (The Mathematical Edge Veto)
        # ==========================================
        # Calculate our baseline risk/reward dollar amounts for the fallback math
        # Assuming our standard 1% risk and 1:3 reward ratio
        baseline_risk_dollars = float(account_balance) * (0.01 * float(risk_multiplier))
        baseline_reward_dollars = baseline_risk_dollars * 3.0

        ev_decision = probability_engine.calculate_regime_ev(
            regime=regime,
            proposed_risk=baseline_risk_dollars,
            proposed_reward=baseline_reward_dollars
        )

        if ev_decision["action"] == "BLOCK":
            logger.warning(f"Trade vetoed by Probability Engine: {ev_decision['reason']}")
            return Response({
                "action": "HOLD",
                "reasoning": f"Math Veto: {ev_decision['reason']}"
            }, status=status.HTTP_200_OK)

        # ==========================================
        # 7. SMART MULTI-LAYERING EVALUATION (Gold Scalper DNA)
        # ==========================================
        layer_decision = layering_engine.calculate_next_layer(
            active_positions=active_positions,
            current_price=current_price,
            atr=atr,
            signal_action=action
        )

        if layer_decision["action"] == "BLOCK_TRADE":
            return Response({"action": "HOLD", "reasoning": layer_decision["reason"]}, status=status.HTTP_200_OK)
            
        elif layer_decision["action"] == "HOLD":
            return Response({"action": "HOLD", "reasoning": layer_decision["reason"]}, status=status.HTTP_200_OK)

        # ==========================================
        # 8. POSITION RISK CALCULATOR
        # ==========================================
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
            return Response({"action": "HOLD", "reasoning": f"Risk engine override: {risk_profile.get('reason')}"}, status=status.HTTP_200_OK)

        final_lots = risk_profile["lots"]
        if layer_decision["action"] == "EXECUTE_LAYER":
            final_lots = layer_decision["target_lots"]

        # ==========================================
        # 9. LOG TO TRADE MEMORY & RESPOND
        # ==========================================
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
            "stop_loss": risk_profile["stop_loss"],
            "take_profit": risk_profile["take_profit"],
            "reasoning": f"[Confidence: {confidence}%] [EV: ${ev_decision.get('ev', 0):.2f}] {reasoning}",
            "market_state_id": state_record.id
        }

        return Response(execution_payload, status=status.HTTP_200_OK)
        
class PerformanceDashboardView(APIView):
    """
    Serves compiled performance aggregations and automated AI 
    self-learning optimization recommendations to the UI.
    """
    permission_classes = [AllowAny] # Set to IsAuthenticated for production

    def get(self, request):
        analytics = PerformanceAnalyticsService()
        metrics = analytics.generate_dashboard_metrics()
        return Response(metrics, status=status.HTTP_200_OK)