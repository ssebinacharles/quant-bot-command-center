import logging
import decimal

logger = logging.getLogger(__name__)

class GoldLayeringEngine:
    """
    The Core Gold Scalper DNA.
    Manages scaling/layering in active positions based on ATR volatility steps.
    Prevents over-leveraging while dynamically scaling into premium entry zones.
    """
    def __init__(self, max_layers: int = 3, grid_step_atr_multiplier: float = 1.5):
        self.max_layers = max_layers
        self.grid_step_multiplier = decimal.Decimal(str(grid_step_atr_multiplier))
        # Lot multiplier for secondary layers (conservative Martingale/scaling)
        self.multiplier = decimal.Decimal("1.5") 

    def calculate_next_layer(self, active_positions: list, current_price: float, atr: float, signal_action: str) -> dict:
        """
        Evaluates open positions of the same type.
        If the market has moved against us by (ATR * multiplier), calculates 
        the price level and exact lot size for the next layered entry.
        """
        if not active_positions:
            # No positions open. We are clear to enter Layer 1.
            return {"action": "ALLOW_NEW_TRADE", "reason": "No active layers exist."}

        # Filter positions matching our current signal direction (BUY/SELL)
        direction_positions = [p for p in active_positions if p.get("type") == signal_action]
        layer_count = len(direction_positions)

        if layer_count >= self.max_layers:
            return {
                "action": "BLOCK_TRADE", 
                "reason": f"Maximum scaling layers ({self.max_layers}) reached. Exposure locked."
            }

        # Find the last entered position price to measure our grid step
        last_entry_price = decimal.Decimal(str(direction_positions[-1]["entry_price"]))
        price = decimal.Decimal(str(current_price))
        volatility_step = decimal.Decimal(str(atr)) * self.grid_step_multiplier

        # Calculate if the price has retraced far enough to warrant Layering
        should_layer = False
        if signal_action == "BUY":
            # For BUYs, we want to buy cheaper (price drops below last entry)
            target_layer_price = last_entry_price - volatility_step
            if price <= target_layer_price:
                should_layer = True
        elif signal_action == "SELL":
            # For SELLs, we want to sell higher (price rises above last entry)
            target_layer_price = last_entry_price + volatility_step
            if price >= target_layer_price:
                should_layer = True

        if not should_layer:
            return {
                "action": "HOLD",
                "reason": f"Grid step not met. Waiting for price to hit deep value zone: {float(target_layer_price) if 'target_layer_price' in locals() else 'N/A'}"
            }

        # Calculate scaled lot size for the next layer
        last_lots = decimal.Decimal(str(direction_positions[-1]["lots"]))
        next_lots = round(last_lots * self.multiplier, 2)

        return {
            "action": "EXECUTE_LAYER",
            "next_layer_index": layer_count + 1,
            "target_lots": float(next_lots),
            "reason": f"Market retraced into premium liquidity. Initiating grid layer {layer_count + 1}."
        }