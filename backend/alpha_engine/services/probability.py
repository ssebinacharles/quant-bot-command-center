from ..models import TradeMemory


class ProbabilityEngine:
    """
    Evaluates expected value (EV) based on historical trade outcomes.
    """

    def calculate_regime_ev(self, regime, proposed_risk=100.0, proposed_reward=300.0):
        trades = TradeMemory.objects.filter(market_state__market_regime=regime, status="CLOSED")

        # Fallback to all closed trades if no specific regime trades exist
        if not trades.exists():
            trades = TradeMemory.objects.filter(status="CLOSED")

        total = trades.count()
        if total == 0:
            return {"ev": 0.0, "action": "ALLOW", "reason": "Gathering data"}

        total_profit = sum(float(t.profit) for t in trades)
        avg_ev = total_profit / total

        if avg_ev <= 0:
            return {
                "ev": avg_ev,
                "action": "BLOCK",
                "reason": "Negative historical expected value"
            }

        return {"ev": avg_ev, "action": "ALLOW", "reason": "Positive EV"}