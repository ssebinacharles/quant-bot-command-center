from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import MarketStateViewSet, TradeMemoryViewSet, TradeExecutionView, PerformanceDashboardView

router = DefaultRouter()
router.register(r'market-states', MarketStateViewSet, basename='marketstate')
router.register(r'trades', TradeMemoryViewSet, basename='tradememory')

urlpatterns = [
    # REST API endpoints for the frontend
    path('', include(router.urls)),
    
    path('dashboard/analytics/', PerformanceDashboardView.as_view(), name='dashboard_analytics'),
    # Live webhook execution channel for the Python MT5 Bridge
    path('engine/execute/', TradeExecutionView.as_view(), name='trade_execute'),
]