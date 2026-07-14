import random
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from alpha_engine.models import MarketState, TradeMemory

class Command(BaseCommand):
    help = 'Seeds the database with historical trades to test the Self-Learning analytics engine.'

    def handle(self, *args, **options):
        self.stdout.write("🧹 Cleaning up old trade records...")
        TradeMemory.objects.all().delete()
        MarketState.objects.all().delete()

        regimes = ['TRENDING_UP', 'TRENDING_DOWN', 'RANGING', 'HIGH_VOLATILITY', 'BULL_CLIMAX', 'BEAR_CLIMAX']
        symbols = ['XAUUSD']
        
        self.stdout.write("🌱 Seeding simulated quant logs...")

        for i in range(30):  # Generate 30 mock trade cycles
            # 1. Create a simulated Market State
            symbol = random.choice(symbols)
            price = Decimal(str(round(random.uniform(2300.00, 2400.00), 2)))
            rsi = Decimal(str(round(random.uniform(20.00, 80.00), 2)))
            atr = Decimal(str(round(random.uniform(1.20, 4.50), 2)))
            regime = random.choice(regimes)

            state = MarketState.objects.create(
                symbol=symbol,
                current_price=price,
                rsi_14=rsi,
                atr_14=atr,
                market_regime=regime,
                gpt_regime_classification="Simulated technical parameters.",
                risk_multiplier=Decimal("1.00")
            )

            # Adjust timestamps historically so they look realistic
            historical_time = timezone.now() - timezone.timedelta(days=30 - i, hours=random.randint(1, 23))
            state.timestamp = historical_time
            state.save()

            # 2. Create a paired Trade Memory
            action = random.choice(['BUY', 'SELL'])
            lots = Decimal("0.05")
            entry_price = price
            
            # Simulate a closed trade outcome
            if action == 'BUY':
                sl = entry_price - (atr * 2)
                tp = entry_price + (atr * 4)
                # Randomize a win or loss
                is_win = random.choices([True, False], weights=[65, 35])[0] if regime in ['TRENDING_UP', 'RANGING'] else random.choices([True, False], weights=[30, 70])[0]
                exit_price = tp if is_win else sl
            else:
                sl = entry_price + (atr * 2)
                tp = entry_price - (atr * 4)
                is_win = random.choices([True, False], weights=[65, 35])[0] if regime in ['TRENDING_DOWN', 'RANGING'] else random.choices([True, False], weights=[30, 70])[0]
                exit_price = tp if is_win else sl

            # Calculate raw profit ($100 per full point on 1.0 standard lot, adjusted for 0.05 lots)
            point_change = (exit_price - entry_price) if action == 'BUY' else (entry_price - exit_price)
            profit = point_change * Decimal("100.00") * lots

            trade = TradeMemory.objects.create(
                market_state=state,
                ticket_id=f"TICKET_{100000 + i}",
                symbol=symbol,
                action=action,
                status='CLOSED',
                lots=lots,
                entry_price=entry_price,
                exit_price=exit_price,
                stop_loss=sl,
                take_profit=tp,
                profit=round(profit, 2),
                ai_confidence_score=Decimal(str(random.randint(60, 95))),
                ai_reasoning=f"Simulation engine aligned with {regime} setups.",
                opened_at=historical_time,
                closed_at=historical_time + timezone.timedelta(hours=random.randint(1, 6))
            )

        self.stdout.write(self.style.SUCCESS("🎉 Database successfully populated with 30 analytical trade cycles!"))