from pythonjsonlogger.json import JsonFormatter
import logging

logger = logging.getLogger("app")

file_handler = logging.FileHandler("app.log")
formatter = JsonFormatter("%(asctime)s %(levelname)s %(message)s")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.setLevel(logging.INFO)
