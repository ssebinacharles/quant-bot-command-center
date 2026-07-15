import logging
import decimal
from django.db.models import Avg, Count
from alpha_engine.models import TradeMemory

logger = logging.getLogger(__name__)

class ProbabilityEngine:
    """
    The Mathematical Edge Filter.
    Calculates the Expected Value (EV) of a specific market regime based on historical execution data.
    Blocks any execution that has a negative mathematical expectation.
    """
    def __init__(self, min_trades_required: int = 5):
        # We need a minimum sample size before we trust the EV math
        self.min_trades_required = min_trades_required

    def calculate_regime_ev(self, regime: str, proposed_risk: float, proposed_reward: float) -> dict:
        """
        Queries the database for historical win rate and average win/loss in the given regime.
        Calculates EV and returns an execution decision.
        """
        # 1. Query historical trades for this specific regime
        historical_trades = TradeMemory.objects.filter(market_state__market_regime=regime, status='CLOSED')
        total_trades = historical_trades.count()

        # If we don't have enough data, default to ALLOW but log a warning
        if total_trades < self.min_trades_required:
            logger.info(f"Probability Engine: Insufficient data for {regime}. Forwarding to standard risk management.")
            return {"action": "ALLOW", "ev": None, "reason": "Gathering data"}

        # 2. Calculate Win Rate (Probability)
        winning_trades = historical_trades.filter(profit__gt=0).count()
        p_win = decimal.Decimal(winning_trades) / decimal.Decimal(total_trades)
        p_loss = decimal.Decimal('1.0') - p_win

        # 3. Calculate Average Win and Loss (Reward/Risk)
        # We use database averages if available, otherwise fallback to the proposed risk/reward of the current setup
        avg_win_data = historical_trades.filter(profit__gt=0).aggregate(Avg('profit'))
        avg_loss_data = historical_trades.filter(profit__lt=0).aggregate(Avg('profit'))

        r_win = avg_win_data['profit__avg'] if avg_win_data['profit__avg'] else proposed_reward
        # Convert loss to a positive absolute number for the formula
        r_loss = abs(avg_loss_data['profit__avg']) if avg_loss_data['profit__avg'] else proposed_risk

        # Convert to Decimals for precision math
        r_win = decimal.Decimal(str(r_win))
        r_loss = decimal.Decimal(str(r_loss))

        # 4. The Expected Value (EV) Equation
        # EV = (P_win * R_win) - (P_loss * R_loss)
        expected_value = (p_win * r_win) - (p_loss * r_loss)

        logger.info(f"[{regime} EV Math] Win Rate: {p_win*100:.2f}% | Avg Win: ${r_win:.2f} | Avg Loss: ${r_loss:.2f} | EV: ${expected_value:.2f}")

        # 5. The Decision Matrix
        if expected_value > 0:
            return {
                "action": "ALLOW",
                "ev": float(expected_value),
                "reason": f"Positive Expected Value (${expected_value:.2f} per trade)."
            }
        else:
            return {
                "action": "BLOCK",
                "ev": float(expected_value),
                "reason": f"Negative Expected Value (${expected_value:.2f}). Statistical edge lost in {regime}."
            }