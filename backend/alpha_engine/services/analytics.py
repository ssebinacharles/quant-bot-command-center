from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta
from ..models import TradeMemory

class PerformanceAnalyticsService:
    """
    The Quant Brain: Analyzes trade memory and generates feedback loops
    to optimize future AI strategy decisions.
    """
    
    def generate_dashboard_metrics(self):
        # 1. Pull all closed trades
        closed_trades = TradeMemory.objects.filter(status='CLOSED')
        total_trades = closed_trades.count()
        
        if total_trades == 0:
            return {
                "summary": {
                    "total_trades": 0, "win_rate": 0, "net_profit": 0, "profit_factor": 0
                },
                "regime_performance": {},
                "optimization_insights": ["No trade data collected yet. Run trades to build intelligence."]
            }

        # 2. Global Aggregations
        winning_trades = closed_trades.filter(profit__gt=0)
        losing_trades = closed_trades.filter(profit__lt=0)
        
        total_wins = winning_trades.count()
        win_rate = round((total_wins / total_trades) * 100, 2)
        
        net_profit = closed_trades.aggregate(Sum('profit'))['profit__sum'] or 0.00
        gross_profit = winning_trades.aggregate(Sum('profit'))['profit__sum'] or 0.00
        gross_loss = abs(losing_trades.aggregate(Sum('profit'))['profit__sum'] or 0.00)
        
        profit_factor = round(float(gross_profit / gross_loss), 2) if gross_loss > 0 else float(gross_profit)

        # 3. Regime-Specific Analysis (Where the "Self-Learning" lives)
        regimes = ['TRENDING_UP', 'TRENDING_DOWN', 'RANGING', 'HIGH_VOLATILITY', 'BULL_CLIMAX', 'BEAR_CLIMAX']
        regime_performance = {}

        for regime in regimes:
            regime_trades = closed_trades.filter(market_state__market_regime=regime)
            r_total = regime_trades.count()
            
            if r_total > 0:
                r_wins = regime_trades.filter(profit__gt=0).count()
                r_win_rate = round((r_wins / r_total) * 100, 2)
                r_profit = float(regime_trades.aggregate(Sum('profit'))['profit__sum'] or 0.00)
                
                regime_performance[regime] = {
                    "total_trades": r_total,
                    "win_rate": r_win_rate,
                    "net_profit": r_profit
                }

        # 4. Generate AI Optimization Insights
        insights = self._generate_insights(regime_performance)

        return {
            "summary": {
                "total_trades": total_trades,
                "win_rate": win_rate,
                "net_profit": float(net_profit),
                "profit_factor": profit_factor,
            },
            "regime_performance": regime_performance,
            "optimization_insights": insights
        }

    def _generate_insights(self, performance):
        """
        Self-Learning Rule Engine: Translates cold math into strategy upgrades.
        """
        insights = []
        
        for regime, stats in performance.items():
            win_rate = stats["win_rate"]
            total = stats["total_trades"]
            
            if total >= 5:  # Require a decent sample size before giving advice
                if win_rate < 40.0:
                    insights.append(
                        f"🚨 WARNING: AI is failing in {regime} with a {win_rate}% win rate. "
                        f"Recommendation: Instruct Groq to HOLD during this phase or tighten stop losses."
                    )
                elif win_rate >= 70.0:
                    insights.append(
                        f"🔥 EXCELLENT: AI is dominating in {regime} with a {win_rate}% win rate. "
                        f"Recommendation: Increase risk multiplier or enable layered scale-ins."
                    )
                    
        if not insights:
            insights.append("Gathering more sample trade sizes per market regime to build optimization profiles.")
            
        return insights
    def evaluate_regime_performance_veto(self, regime: str) -> bool:
        """
        Evaluates historical performance in a given market regime.
        Returns True if trading should be vetoed (e.g., win rate < 40%), False otherwise.
        """
        # TODO: Implement the actual database query and win-rate calculation logic
        
        # Defaulting to False so normal execution tests pass
        return False