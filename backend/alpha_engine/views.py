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

        # ==========================================
        # 1. GLOBAL PORTFOLIO DRAWDOWN GUARD (The Breaker)
        # ==========================================
        portfolio_status = portfolio_manager.evaluate_portfolio_safety(
            account_balance=account_balance,
            current_equity=current_equity
        )
        
        if portfolio_status["circuit_breaker_active"]:
            logger.critical("EMERGENCY INTERVENTION: Daily Drawdown Limit Breached. Sending Flatten request.")
            return Response({
                "action": "FLATTEN_ALL",
                "reasoning": f"DAILY DRAWDOWN MITIGATION: Enforcing hard stop. Daily Loss: ${abs(portfolio_status['total_daily_pnl'])}."
            }, status=status.HTTP_200_OK)

        # ==========================================
        # 2. MARKET REGIME DETECTION
        # ==========================================
        regime, risk_multiplier = brain.detect_regime(rsi, atr, current_price)

        # ==========================================
        # 3. SELF-LEARNING VETO LOOP
        # ==========================================
        performance_data = analytics.generate_dashboard_metrics()
        regime_stats = performance_data.get("regime_performance", {}).get(regime, {})
        
        if regime_stats:
            total_regime_trades = regime_stats.get("total_trades", 0)
            regime_win_rate = regime_stats.get("win_rate", 100.0)
            if total_regime_trades >= 5 and regime_win_rate < 40.0:
                return Response({
                    "action": "HOLD",
                    "reasoning": f"Self-Learning Block: Bypassing execution in {regime} due to a poor {regime_win_rate}% win rate."
                }, status=status.HTTP_200_OK)

        # ==========================================
        # 4. ACTIVE POSITION MANAGMENT & DYNAMIC EXIT STRATEGY
        # ==========================================
        exit_signal = brain.evaluate_active_exits(active_positions, rsi, regime)
        if exit_signal:
            return Response(exit_signal, status=status.HTTP_200_OK)

        # ==========================================
        # 5. CONSULT AI DECISION PIPELINE (Get direction)
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
        # 6. SMART MULTI-LAYERING EVALUATION (Gold Scalper DNA)
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
        # 7. POSITION RISK CALCULATOR
        # ==========================================
        # Scale our base risk % relative to current market regime volatility
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

        # Override lot sizing if the Multi-Layering engine calculated a scaled Grid Entry
        final_lots = risk_profile["lots"]
        if layer_decision["action"] == "EXECUTE_LAYER":
            final_lots = layer_decision["target_lots"]
            logger.info(f"Layering active. Overriding entry lots to: {final_lots}")

        # ==========================================
        # 8. LOG TO TRADE MEMORY & RESPOND
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
            "reasoning": f"[Confidence: {confidence}%] {reasoning}",
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