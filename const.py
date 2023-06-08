"""Constants for the Vakio Smart Control integration."""
import datetime
from homeassistant.const import Platform

DOMAIN = "vakio_smart_control"

# Platform
PLATFORMS = [
    Platform.SENSOR,
    Platform.FAN
]

# Default consts.
DEFAULT_PORT = 1883
DEFAULT_TOPIC = "vakio"
DEFAULT_TIMEINTERVAL = datetime.timedelta(seconds=5)

# CONF consts.
CONF_HOST = "host"
CONF_PORT = "port"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_TOPIC = "topic"

# Errors.
ERROR_AUTH: str = "ошибка аутентификации"
ERROR_CONFIG_NO_TREADY: str = "конфигурация интеграции не готова"
