from celery import shared_task
from decimal import Decimal
from django.utils import timezone
from data_ingestion.services import FeatureEngineeringService
from alpha_engine.agents.scalper import GroqScalperAgent
from alpha_engine.models import TradeLog
import logging
import uuid

logger = logging.getLogger(__name__)

@shared_task(name='alpha_engine.tasks.execute_scalper_loop')
def execute_scalper_loop():
    """
    The main autonomous execution circuit matching indicators to AI processing
    and writing the outcomes to the historical data layer.
    """
    logger.info("Executing autonomous trading loop sequence...")
    
    try:
        # 1. Gather raw data and build the 10x6 sequence matrix
        data_service = FeatureEngineeringService()
        mock_bars = data_service.generate_simulation_data(base_price=2350.0, bars=40)
        normalized_matrix = data_service.calculate_normalized_features(mock_bars)
        
        # 2. Hand the processed matrix to the Groq LPU engine
        agent = GroqScalperAgent()
        ai_response = agent.analyze_market_sequence(normalized_matrix)
        
        action = ai_response.get("action", "HOLD")
        confidence = ai_response.get("confidence", 0)
        reason = ai_response.get("reason", "No context provided.")
        
        logger.info(f"Groq Engine Decision: {action} | Confidence: {confidence}%")
        
        # 3. Commit action execution states directly into the database
        if action in ['BUY', 'SELL']:
            current_price = mock_bars['close'].iloc[-1]
            ticket = str(uuid.uuid4().int)[:8] # Generate a clean unique mock ticket ID
            
            trade = TradeLog.objects.create(
                ticket_id=f"MT5_{ticket}",
                symbol="XAUUSD",
                action=action,
                status="OPEN", # Leaves it open to emulate an active market position
                lots=Decimal("0.10"),
                entry_price=Decimal(str(round(current_price, 2))),
                ai_confidence_score=Decimal(str(confidence)),
                raw_groq_response=ai_response,
                feature_snapshot={"matrix_tail": normalized_matrix[-1]}
            )
            logger.info(f"Database position recorded successfully: Ticket {trade.ticket_id}")
            return f"Executed {action} position successfully."
            
        logger.info("Signal evaluated to HOLD. Position skipped.")
        return "Evaluated state: HOLD"
        
    except Exception as e:
        logger.error(f"Automation execution loop failed: {str(e)}")
        return f"Execution failure: {str(e)}"