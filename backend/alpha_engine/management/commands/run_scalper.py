import time
from decimal import Decimal
from django.core.management.base import BaseCommand
from data_ingestion.services import XAUUSDMarketSimulator, FeatureEngineeringService
from alpha_engine.ai_agent import GroqTradingAgent
from alpha_engine.models import TradeLog 

class Command(BaseCommand):
    help = "Runs the live AI scalper feature pipeline and execution loop"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Starting Alpha Engine core execution terminal..."))
        
        # Initialize your real services side-by-side
        market_feed = XAUUSDMarketSimulator()
        feature_pipeline = FeatureEngineeringService()
        ai_agent = GroqTradingAgent()

        for tick in range(5):
            self.stdout.write(f"\n--- Processing Market Frame {tick + 1} ---")
            
            # 1. Fetch market dataframe
            df_m5 = market_feed.generate_market_dataframe()
            
            # Keep as a standard float for logs, convert to Decimal for the DB
            latest_close = float(df_m5['close'].iloc[-1])
            self.stdout.write(f"Current XAUUSD Spot Price: ${latest_close}")

            # 2. Run your real custom feature engineering math!
            try:
                # Passing data straight through your pipeline
                engineered_features = feature_pipeline.calculate_normalized_features(df_m5)
                self.stdout.write("Features successfully engineered using Pandas pipeline.")
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Feature engine skipped calculations: {e}"))
                engineered_features = None

            # 3. Compile a metrics package for the AI agent
            market_state = {
                "symbol": "XAUUSD",
                "bid": latest_close,
                "ask": round(latest_close + 0.25, 2),
                "trend": "UPWARD" if float(df_m5['close'].iloc[-1]) > float(df_m5['close'].iloc[-5]) else "DOWNWARD",
                "sma_10": round(float(df_m5['close'].tail(10).mean()), 2)
            }

            # 4. Trigger the AI Scalper Decision Engine
            decision = ai_agent.analyze_market(market_state)
            self.stdout.write(f"Groq Trade Directive: {decision['action']} | Confidence: {decision['confidence']}%")

           # 5. Save execution metrics directly to your Django Database
            if decision['action'] in ['BUY', 'SELL']:
                try:
                    # Generate a unique 8-digit mock broker ticket number for simulation
                    import random
                    mock_ticket_id = random.randint(10000000, 99999999)

                    TradeLog.objects.create(
                        ticket_id=mock_ticket_id,                         # Fixes the UNIQUE constraint error
                        symbol="XAUUSD",
                        action=decision['action'],
                        entry_price=Decimal(str(latest_close)),
                        lots=Decimal("0.10"),
                        ai_confidence_score=int(decision['confidence']),
                        raw_groq_response={"reason": decision['reason']},
                        feature_snapshot=market_state 
                    )
                    self.stdout.write(self.style.SUCCESS(f"Trade record {mock_ticket_id} verified and pushed to live dashboard database!"))
                except Exception as db_err:
                    self.stdout.write(self.style.ERROR(f"Database insertion failed: {db_err}"))
            time.sleep(4)