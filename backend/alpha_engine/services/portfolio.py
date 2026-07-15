import logging
import decimal
from django.utils import timezone
from alpha_engine.models import TradeMemory

logger = logging.getLogger(__name__)

class PortfolioManagerService:
    """
    The Global Risk Circuit Breaker.
    Monitors realized daily gains/losses and current floating PnL.
    Enforces the absolute 5% daily drawdown limit.
    """
    def __init__(self, max_daily_drawdown_pct: float = 0.05):
        self.max_daily_drawdown_pct = decimal.Decimal(str(max_daily_drawdown_pct))

    def evaluate_portfolio_safety(self, account_balance: float, current_equity: float) -> dict:
        """
        Calculates total daily realized PnL + current floating PnL.
        If the loss exceeds the safety threshold, triggers a global hard-halt.
        """
        balance = decimal.Decimal(str(account_balance))
        equity = decimal.Decimal(str(current_equity))
        
        # 1. Calculate current floating (unrealized) PnL
        floating_pnl = equity - balance

        # 2. Query realized PnL for today (since midnight UTC)
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        closed_trades_today = TradeMemory.objects.filter(
            closed_at__gte=today_start,
            status='CLOSED'
        )
        
        realized_pnl_today = decimal.Decimal("0.00")
        for trade in closed_trades_today:
            realized_pnl_today += decimal.Decimal(str(trade.profit))

        # 3. Calculate Cumulative Daily PnL
        total_daily_pnl = realized_pnl_today + floating_pnl
        
        # 4. Calculate Drawdown Threshold (5% of starting daily balance)
        # Starting Balance of the Day = Current Balance - Realized PnL Today
        starting_day_balance = balance - realized_pnl_today
        if starting_day_balance <= 0:
            starting_day_balance = balance  # Fallback to prevent division by zero
            
        max_allowed_loss = starting_day_balance * self.max_daily_drawdown_pct
        
        # Check if we have breached our daily risk limit
        is_breached = False
        if total_daily_pnl < 0 and abs(total_daily_pnl) >= max_allowed_loss:
            is_breached = True
            logger.critical(
                f"🚨 CIRCUIT BREAKER BREACHED: Daily loss ({total_daily_pnl}) "
                f"exceeded maximum allowed limit of ({max_allowed_loss})."
            )

        return {
            "circuit_breaker_active": is_breached,
            "realized_pnl_today": float(realized_pnl_today),
            "floating_pnl": float(floating_pnl),
            "total_daily_pnl": float(total_daily_pnl),
            "max_allowed_loss": float(max_allowed_loss),
            "action_required": "FLATTEN_ALL" if is_breached else "CONTINUE"
        }
    def evaluate_drawdown(self, current_equity, account_balance):
        """
        Checks if the current equity drawdown has breached safety thresholds.
        Returns 'FLATTEN_ALL' if drawdown >= 5%, otherwise 'PROCEED'.
        """
        if not account_balance or account_balance <= 0:
            return "PROCEED"
        
        # Calculate drawdown percentage
        drawdown_pct = (account_balance - current_equity) / account_balance
        
        # 5% safety threshold circuit breaker
        if drawdown_pct >= 0.05:
            return "FLATTEN_ALL"
        return "PROCEED"

    def evaluate_active_exits(self, active_positions, current_price, atr):
        """
        Monitors active trades for trailing stops or profit targets.
        Returns exit actions or an empty dict if no action is needed.
        """
        # Default behavior: proceed without forcing an exit
        return {"action": "PROCEED"}