import logging
from decimal import Decimal

logger = logging.getLogger(__name__)

class RiskManagerService:
    """
    The Safety Gatekeeper. Calculates absolute risk parameters, 
    dynamic volatility-based stop-losses, and precise asset lot sizing.
    """
    def __init__(self, max_risk_pct: float = 0.01, max_daily_drawdown_pct: float = 0.05):
        # Default settings: Risk 1% of account per trade, max 5% daily drawdown limit
        self.max_risk_pct = Decimal(str(max_risk_pct))
        self.max_daily_drawdown_pct = Decimal(str(max_daily_drawdown_pct))

    def evaluate_and_size_trade(self, account_balance: float, entry_price: float, atr: float, action: str, symbol: str = "XAUUSD") -> dict:
        """
        Processes a trade signal and builds a definitive risk configuration payload.
        Uses Average True Range (ATR) for volatility-adjusted stop losses.
        """
        # Fallback for neutral holds
        if action not in ["BUY", "SELL"]:
            return {"status": "REJECTED", "reason": "Action is HOLD, skipping evaluation."}

        balance = Decimal(str(account_balance))
        entry = Decimal(str(entry_price))
        volatility = Decimal(str(atr))

        if balance <= 0:
            return {"status": "REJECTED", "reason": "Account balance is zero or negative."}

        # 1. Determine Cash Risk Amount (e.g., 1% of $1,000 = $10)
        cash_at_risk = balance * self.max_risk_pct

        # 2. Calculate Stop Loss Distance using standard 2x ATR multiplier
        sl_distance = volatility * Decimal("2.0")
        
        if action == "BUY":
            stop_loss = entry - sl_distance
            take_profit = entry + (sl_distance * Decimal("3.0"))  # Strict 1:3 Risk-to-Reward ratio
        else:  # SELL
            stop_loss = entry + sl_distance
            take_profit = entry - (sl_distance * Decimal("3.0"))

        # 3. Calculate Contract Lot Sizing based on Asset Type
        # Standard Contract size rules: Gold (XAUUSD) = 100 ounces per standard lot.
        if "XAUUSD" in symbol.upper():
            contract_size = Decimal("100")
        else:
            contract_size = Decimal("100000")  # Default standard Forex lot size

        # Formula: Lot Size = Cash Risk / (SL Distance * Contract Size)
        try:
            calculated_lots = cash_at_risk / (sl_distance * contract_size)
            # Round down to 2 decimal places (broker standard for lot sizes)
            final_lots = max(Decimal("0.01"), round(calculated_lots, 2))
        except ZeroDivisionError:
            return {"status": "REJECTED", "reason": "Volatility reading is 0. Cannot compute risk metrics."}

        # 4. Final Security Check: Prevent excessively massive position spikes
        if final_lots > Decimal("5.00"):
            logger.warning(f"Calculated size {final_lots} exceeds maximum safety ceiling. Capping position.")
            final_lots = Decimal("1.00")

        return {
            "status": "APPROVED",
            "action": action,
            "symbol": symbol,
            "entry_price": float(entry),
            "lots": float(final_lots),
            "stop_loss": float(round(stop_loss, 2 if "XAUUSD" in symbol.upper() else 5)),
            "take_profit": float(round(take_profit, 2 if "XAUUSD" in symbol.upper() else 5)),
            "cash_at_risk": float(round(cash_at_risk, 2))
        }