import logging
from ..models import TradeMemory

logger = logging.getLogger(__name__)

class ExecutionRouter:
    """
    Handles order routing for both Paper Trading and Live Execution.
    Calculates dynamic position sizing based on risk multipliers.
    """

    def __init__(self, mode="PAPER", base_risk_usd=100.0):
        self.mode = mode  # "PAPER" or "LIVE"
        self.base_risk_usd = base_risk_usd

    def execute_order(self, symbol, current_price, regime, risk_multiplier, rsi, atr):
        # 1. Calculate dynamic risk & position bounds
        allocated_risk = self.base_risk_usd * risk_multiplier
        stop_loss_distance = atr * 1.5  # Volatility-based stop distance
        take_profit_distance = atr * 3.0 # 2:1 Reward-to-Risk ratio

        # Determine direction based on regime
        side = "BUY" if "UP" in regime or rsi > 50 else "SELL"

        if side == "BUY":
            stop_loss = round(current_price - stop_loss_distance, 2)
            take_profit = round(current_price + take_profit_distance, 2)
        else:
            stop_loss = round(current_price + stop_loss_distance, 2)
            take_profit = round(current_price - take_profit_distance, 2)

        position_size = round(allocated_risk / stop_loss_distance, 4) if stop_loss_distance > 0 else 0.01

        order_details = {
            "symbol": symbol,
            "side": side,
            "entry_price": current_price,
            "size": position_size,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "allocated_risk": allocated_risk,
            "regime": regime,
            "mode": self.mode
        }

        # 2. Route order based on execution mode
        if self.mode == "PAPER":
            return self._execute_paper_trade(order_details)
        elif self.mode == "LIVE":
            return self._execute_live_trade(order_details)
        else:
            raise ValueError(f"Invalid execution mode: {self.mode}")

    def _execute_paper_trade(self, order):
        """Simulates order fill and stores open trade in Django database."""
        trade = TradeMemory.objects.create(
            symbol=order["symbol"],
            side=order["side"],
            entry_price=order["entry_price"],
            position_size=order["size"],
            stop_loss=order["stop_loss"],
            take_profit=order["take_profit"],
            status="OPEN",
            profit=0.0
        )
        logger.info(f"[PAPER EXECUTION] Created Trade #{trade.id} for {order['symbol']} @ {order['entry_price']}")
        return {
            "status": "EXECUTED",
            "trade_id": trade.id,
            "details": order
        }

    def _execute_live_trade(self, order):
        """
        Stub for broker API integration (e.g., Binance, Bybit, Alpaca, or CCXT).
        """
        # TODO: Instantiate exchange client and send real order payload
        logger.warning(f"[LIVE EXECUTION STUB] Order passed to live router: {order}")
        return {
            "status": "LIVE_SUBMITTED",
            "details": order
        }