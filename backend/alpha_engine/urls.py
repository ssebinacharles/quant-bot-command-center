from django.urls import path, include
from rest_framework.routers import DefaultRouter
# Make sure TradeExecutionView is explicitly added to this import line:
from .views import TradeLogViewSet, MarketRegimeViewSet, TradeExecutionView

router = DefaultRouter()
router.register(r'trades', TradeLogViewSet, basename='trade-logs')
router.register(r'regimes', MarketRegimeViewSet, basename='market-regimes')

urlpatterns = [
    path('', include(router.urls)),
    
    # Injects the custom API execution route
    path('engine/execute/', TradeExecutionView.as_view(), name='engine-execute'),
]