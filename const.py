"""Constants for the Vakio Smart Control integration."""
import datetime
from homeassistant.const import Platform

DOMAIN = "vakio_smart_control"

# Platform
# PLATFORMS = [Platform.SENSOR, Platform.FAN]
PLATFORMS = [Platform.SENSOR, Platform.CLIMATE]

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

CONNECTION_TIMEOUT = 5

# Open Air
OPENAIR_STATE_ON = "on"
OPENAIR_STATE_OFF = "off"
OPENAIR_WORKMODE_MANUAL = "manual"
OPENAIR_WORKMODE_SUPERAUTO = "super_auto"
OPENAIR_SPEED_00 = 0
OPENAIR_SPEED_01 = 1
OPENAIR_SPEED_02 = 2
OPENAIR_SPEED_03 = 3
OPENAIR_SPEED_04 = 4
OPENAIR_SPEED_05 = 5
OPENAIR_SPEED_LIST = [
    OPENAIR_SPEED_00,
    OPENAIR_SPEED_01,
    OPENAIR_SPEED_02,
    OPENAIR_SPEED_03,
    OPENAIR_SPEED_04,
    OPENAIR_SPEED_05,
]
OPENAIR_GATE_01 = 1
OPENAIR_GATE_02 = 2
OPENAIR_GATE_03 = 3
OPENAIR_GATE_04 = 4
OPENAIR_GATE_LIST = [
    OPENAIR_GATE_01,
    OPENAIR_GATE_02,
    OPENAIR_GATE_03,
    OPENAIR_GATE_04,
]
