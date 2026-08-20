DOMAIN = "evcc_trial_token_updater"

CONF_EVCC_URL = "evcc_url"
CONF_API_KEY = "api_key"
CONF_ENABLED = "enabled"
CONF_INTERVAL = "interval_hours"
CONF_AUTO_RESTART = "auto_restart"
CONF_UPDATE_TIME = "update_time"
CONF_SKIP_WHILE_CHARGING = "skip_while_charging"

DEFAULT_INTERVAL = 12
DEFAULT_AUTO_RESTART = True
DEFAULT_UPDATE_TIME = "02:00"
DEFAULT_SKIP_WHILE_CHARGING = True

DOC_URL = "https://docs.evcc.io/en/sponsorship/"
SPONSOR_TOKEN_PATH = "/api/config/sponsortoken"
SHUTDOWN_PATH = "/api/system/shutdown"
STATE_PATH = "/api/state"
DB_BACKUP_PATH = "/api/db/backup"

STATUS_STARTING = "starting"
STATUS_ALREADY_CURRENT = "already_current"
STATUS_UPDATE_AVAILABLE = "update_available"
STATUS_UPDATED = "updated"
STATUS_UPDATED_RESTART_REQUESTED = "updated_restart_requested"
STATUS_CURRENT_UNKNOWN = "current_token_unknown"
STATUS_SKIPPED_CHARGING = "skipped_while_charging"
STATUS_ERROR = "error"

VERSION = "1.0.0"
