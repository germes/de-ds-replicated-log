import logging

logging.basicConfig(
    filename='/usr/src/log/app.log',
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger()
