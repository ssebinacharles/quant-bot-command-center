from django.urls import path, include
from rest_framework.routers import DefaultRouter
from alpha_engine.views import TradeLogViewSet

router = DefaultRouter()
router.register(r'trades', TradeLogViewSet, basename='trade-logs')

urlpatterns = [
    path('', include(router.urls)),
]