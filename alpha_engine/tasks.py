from celery import shared_task
import logging

logger = logging.getLogger(__name__)

@shared_task
def test_system_heartbeat():
    logger.info("-- QUANT BOT HESRTBEAT: CODESPACE ALIVE  --")
    return "Codespaces Heartbeat Verification Successfully"