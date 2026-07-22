import logging
from decimal import Decimal
from celery import shared_task
from alpha_engine.agents.scalper import GroqScalperAgent
from .models import TradeMemory

logger = logging.getLogger(__name__)


@shared_task(name='alpha_engine.tasks.evaluate_live_market')
def evaluate_live_market(market_payload):
    """
    Receives live candle/indicator data from mt5_bridge.py, passes it to the
    Groq LPU engine, and returns a BUY, SELL, or HOLD action.
    """
    logger.info(f"Evaluating live market data for {market_payload.get('symbol', 'XAUUSD')}...")
    
    try:
        agent = GroqScalperAgent()
        
        # Hand the live sequence matrix from MT5 directly to Groq
        matrix = market_payload.get("normalized_matrix")
        ai_response = agent.analyze_market_sequence(matrix)
        
        action = ai_response.get("action", "HOLD")
        confidence = ai_response.get("confidence", 0)
        
        logger.info(f"Groq Engine Live Decision: {action} | Confidence: {confidence}%")
        
        return {
            "action": action,
            "confidence": confidence,
            "raw_response": ai_response
        }
        
    except Exception as e:
        logger.error(f"Live evaluation failed: {str(e)}")
        return {"action": "HOLD", "confidence": 0, "error": str(e)}


@shared_task(name='alpha_engine.tasks.record_executed_trade')
def record_executed_trade(trade_data):
    """
    Triggered ONLY after mt5_bridge.py confirms a trade was successfully 
    placed on the MetaTrader 5 demo account. Logs the real broker ticket.
    """
    try:
        trade = TradeMemory.objects.create(
            ticket_id=str(trade_data.get("ticket_id")), # Real MT5 ticket number
            symbol=trade_data.get("symbol", "XAUUSD"),
            action=trade_data.get("action"),
            status="OPEN",
            lots=Decimal(str(trade_data.get("lots", "0.10"))),
            entry_price=Decimal(str(trade_data.get("entry_price"))),
            ai_confidence_score=Decimal(str(trade_data.get("confidence", 0))),
            raw_groq_response=trade_data.get("raw_groq_response", {}),
            feature_snapshot=trade_data.get("feature_snapshot", {})
        )
        logger.info(f"Successfully recorded LIVE MT5 position: Ticket {trade.ticket_id}")
        return f"Logged Ticket {trade.ticket_id}"
    except Exception as e:
        logger.error(f"Failed to record live trade: {str(e)}")
        return f"Database logging error: {str(e)}"