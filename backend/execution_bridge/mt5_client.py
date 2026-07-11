import MetaTrader5 as mt5
import logging

def initialize_mt5():
    """Establish a connection with the MetaTrader 5 terminal."""
    if not mt5.initialize():
        logging.error("MT5 initialization failed")
        mt5.shutdown()
        return False
    return True

def execute_trade(symbol, lot_size, order_type):
    """Send a request to perform a trading operation."""
    if not initialize_mt5():
        return None

    # Example: Basic market order structure
    action = mt5.ORDER_TYPE_BUY if order_type == 'BUY' else mt5.ORDER_TYPE_SELL
    price = mt5.symbol_info_tick(symbol).ask if order_type == 'BUY' else mt5.symbol_info_tick(symbol).bid

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": float(lot_size),
        "type": action,
        "price": price,
        "deviation": 10, # Slippage tolerance
        "magic": 234000, # Unique ID for your bot
        "comment": "AI Quant Order",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    
    result = mt5.order_send(request)
    return result