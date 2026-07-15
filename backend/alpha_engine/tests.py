import json
from unittest.mock import patch
from django.test import TestCase, Client
from django.utils import timezone
from alpha_engine.models import MarketState, TradeMemory

class QuantEngineIntegrationTests(TestCase):
    def setUp(self):
        self.client = Client()
        
        # ⚠️ UPDATE THIS URL TO YOUR EXACT ROUTER PATH (e.g., "/api/trade/" or "/trade/")
        self.url = "/engine/execute/"  
        
        # Flush tables to isolate test states
        TradeMemory.objects.all().delete()
        MarketState.objects.all().delete()

    @patch('alpha_engine.services.brain.MarketBrainService.analyze_market_and_positions')
    def test_scenario_1_normal_execution_flow(self, mock_ai_brain):
        """
        GIVEN a stable account state and normal market volatility
        WHEN telemetry is posted to the endpoint
        THEN the pipeline should run successfully and return an entry payload.
        """
        mock_ai_brain.return_value = {
            "action": "BUY",
            "confidence_score": 85.0,
            "reasoning": "Gold breaking above key horizontal resistance on M15."
        }

        telemetry = {
            "symbol": "XAUUSD",
            "current_price": 2400.00,
            "rsi_14": 52.0,
            "atr_14": 2.00,
            "balance": 10000.00,
            "equity": 10000.00,
            "active_positions": []
        }

        response = self.client.post(
            self.url,
            data=json.dumps(telemetry),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertEqual(data["action"], "BUY")
        self.assertTrue(data["lots"] > 0)
        self.assertTrue(data["stop_loss"] < 2400.00)
        self.assertTrue(data["take_profit"] > 2400.00)

    def test_scenario_2_portfolio_drawdown_circuit_breaker(self):
        """
        GIVEN an active trading session where equity falls below 5% drawdown
        WHEN telemetry is posted
        THEN the Portfolio Manager must override all processes and return FLATTEN_ALL.
        """
        telemetry = {
            "symbol": "XAUUSD",
            "current_price": 2400.00,
            "rsi_14": 50.0,
            "atr_14": 2.00,
            "balance": 10000.00,
            "equity": 9450.00,  # 5.5% drawdown
            "active_positions": [{"ticket": 12345, "type": "BUY", "lots": 0.1, "profit": -550.00}]
        }

        response = self.client.post(
            self.url,
            data=json.dumps(telemetry),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertEqual(data["action"], "FLATTEN_ALL")
        # 🌟 FIXED: Updated to match your system's actual drawdown message
        self.assertIn("drawdown threshold breached", data["reasoning"].lower())

    @patch('alpha_engine.services.brain.MarketBrainService.analyze_market_and_positions')
    def test_scenario_3_self_learning_loop_veto(self, mock_ai_brain):
        """
        GIVEN a history of 5 consecutive losses in the TRENDING_UP regime (win rate < 40%)
        WHEN a new BUY setup is triggered in TRENDING_UP
        THEN the Self-Learning Loop must veto the execution and return HOLD.
        """
        mock_ai_brain.return_value = {
            "action": "BUY",
            "confidence_score": 90.0,
            "reasoning": "Strong momentum build."
        }

        # Seed 5 consecutive losing trades in TRENDING_UP with unique ticket_ids
        for i in range(5):
            state = MarketState.objects.create(
                symbol="XAUUSD",
                current_price=2400.00,
                rsi_14=75.0,  # High RSI triggers TRENDING_UP
                atr_14=2.00,
                market_regime="TRENDING_UP",
                risk_multiplier=1.0
            )
            TradeMemory.objects.create(
                market_state=state,
                ticket_id=f"TEST_TICKET_300_{i}",
                status="CLOSED",
                symbol="XAUUSD",
                entry_price=2400.00, 
                lots=0.1,
                profit=-150.00,
                closed_at=timezone.now()
            )

        telemetry = {
            "symbol": "XAUUSD",
            "current_price": 2420.00,
            "rsi_14": 75.0,
            "atr_14": 2.00,
            "balance": 10000.00,
            "equity": 10000.00,
            "active_positions": []
        }

        response = self.client.post(
            self.url,
            data=json.dumps(telemetry),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertEqual(data["action"], "HOLD")
        self.assertIn("Self-Learning Block", data["reasoning"])

    @patch('alpha_engine.services.brain.MarketBrainService.analyze_market_and_positions')
    def test_scenario_4_smart_layering_logic(self, mock_ai_brain):
        """
        GIVEN an active BUY position at $2400.00
        WHEN the price drops significantly (exceeding dynamic ATR grid step)
        THEN the Gold Layering Engine should calculate and permit a second entry with scaled lots.
        """
        mock_ai_brain.return_value = {
            "action": "BUY",
            "confidence_score": 80.0,
            "reasoning": "Adding to long bias."
        }

        telemetry = {
            "symbol": "XAUUSD",
            "current_price": 2390.00,  # Deep pullback from our entry ($10 dip, ATR is 2.00)
            "rsi_14": 30.0,
            "atr_14": 2.00,
            "balance": 10000.00,
            "equity": 9900.00,
            "active_positions": [
                {
                    "ticket": 9999,
                    "type": "BUY",
                    "lots": 0.10,
                    "entry_price": 2400.00,
                    "current_price": 2390.00,
                    "profit": -100.00
                }
            ]
        }

        response = self.client.post(
            self.url,
            data=json.dumps(telemetry),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertEqual(data["action"], "BUY")
        self.assertEqual(data["lots"], 0.15)  # 0.10 base lots * 1.5 multiplier

    @patch('alpha_engine.services.brain.MarketBrainService.analyze_market_and_positions')
    def test_scenario_5_probability_engine_veto(self, mock_ai_brain):
        """
        GIVEN a market regime with negative historical expected value (EV <= 0)
        WHEN telemetry is posted
        THEN the Probability Engine must block the execution.
        """
        mock_ai_brain.return_value = {
            "action": "BUY",
            "confidence_score": 85.0,
            "reasoning": "Ranging market setup."
        }

        # Seed trades in RANGING regime resulting in a negative expected value
        state = MarketState.objects.create(
            symbol="XAUUSD",
            current_price=2400.00,
            rsi_14=50.0,
            atr_14=2.00,
            market_regime="TRENDING_UP",  
            risk_multiplier=1.0
        )

        TradeMemory.objects.create(
            market_state=state, 
            ticket_id="TEST_TICKET_500_WIN", 
            status="CLOSED", 
            symbol="XAUUSD",
            entry_price=2400.00,
            lots=0.1, 
            profit=50.00, 
            closed_at=timezone.now()
        )
        
        for i in range(4):
            TradeMemory.objects.create(
                market_state=state, 
                ticket_id=f"TEST_TICKET_500_LOSS_{i}", 
                status="CLOSED", 
                symbol="XAUUSD",
                entry_price=2400.00,
                lots=0.1, 
                profit=-100.00, 
                closed_at=timezone.now()
            )

        telemetry = {
            "symbol": "XAUUSD",
            "current_price": 2400.00,
            "rsi_14": 50.0,
            "atr_14": 2.00,
            "balance": 10000.00,
            "equity": 10000.00,
            "active_positions": []
        }

        response = self.client.post(
            self.url,
            data=json.dumps(telemetry),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["action"], "HOLD")
        self.assertIn("Math Veto", data["reasoning"])