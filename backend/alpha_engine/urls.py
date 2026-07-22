from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    MarketStateViewSet, 
    TradeMemoryViewSet, 
    TradeExecutionView, 
    PerformanceDashboardView,
    evaluate_market_view, 
    record_trade_view
)

router = DefaultRouter()
router.register(r'market-states', MarketStateViewSet, basename='marketstate')
router.register(r'trades', TradeMemoryViewSet, basename='tradememory')

urlpatterns = [
    # REST API endpoints for the React frontend dashboard
    path('', include(router.urls)),
    
    path('dashboard/analytics/', PerformanceDashboardView.as_view(), name='dashboard_analytics'),
    
    # Live execution & evaluation channels for the Python MT5 Bridge
    path('engine/execute/', TradeExecutionView.as_view(), name='trade_execute'),
    path('evaluate/', evaluate_market_view, name='evaluate-live-market'),
    path('log-trade/', record_trade_view, name='log-executed-trade'),
]