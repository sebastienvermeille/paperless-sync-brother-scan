# console handler
import logging
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)
# errors/warnings handler in error file
errors_handler = logging.FileHandler('errors.log')
errors_handler.setLevel(logging.WARN)
errors_handler.setFormatter(formatter)

logger = logging.getLogger('syncScanLogger')
logger.setLevel(logging.INFO)
logger.addHandler(console_handler)
logger.addHandler(errors_handler)
