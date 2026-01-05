"""Application constants.

Centralized location for all magic numbers and strings previously scattered
throughout the codebase.
"""

from PySide6.QtCore import Qt

# ============================================================================
# API Configuration
# ============================================================================

# USDA API timeouts (seconds)
API_CONNECT_TIMEOUT = 3.05
API_READ_TIMEOUT_DEFAULT = 20.0
API_READ_TIMEOUT_IMPORT = 8.0
API_READ_TIMEOUT_ADD = 8.0

# Retry configuration
API_MAX_RETRY_ATTEMPTS = 4
API_RETRY_BACKOFF_FACTOR = 1.0
API_RETRY_STATUS_CODES = (429, 500, 502, 503, 504)

# Connection pooling
API_POOL_CONNECTIONS = 8
API_POOL_MAXSIZE = 8

# USDA API endpoints
USDA_API_BASE_URL = "https://api.nal.usda.gov/fdc/v1"

# ============================================================================
# Search Configuration
# ============================================================================

# Pagination
SEARCH_PAGE_SIZE_DEFAULT = 25
SEARCH_FETCH_PAGE_SIZE = 200
SEARCH_MAX_PAGES = 5

# ============================================================================
# Data Type Priority
# ============================================================================

# Lower number = higher priority for search results
DATA_TYPE_PRIORITY = {
    "Foundation": 0,
    "SR Legacy": 1,
    "Survey": 2,
    "Survey (FNDDS)": 2,
    "Experimental": 3,
    "Branded": 4,
}

# ============================================================================
# Qt Custom Roles
# ============================================================================

# Custom data roles for QTableWidget items
FAT_ROW_ROLE = Qt.UserRole + 501
HEADER_SPAN_ROLE = Qt.UserRole + 502

# ============================================================================
# Table Column Indices (Original UI)
# ============================================================================

# Ingredients table
INGREDIENTS_NAME_COLUMN = 0
INGREDIENTS_AMOUNT_G_COLUMN = 2
INGREDIENTS_PERCENT_COLUMN = 3
INGREDIENTS_LOCK_COLUMN = 4

# ============================================================================
# Nutrient Calculation Constants
# ============================================================================

# Atwater factors (kcal per gram)
ATWATER_PROTEIN = 4.0
ATWATER_CARBOHYDRATE = 4.0
ATWATER_FAT = 9.0

# Conversion factors
KCAL_TO_KJ = 4.184
PROTEIN_TO_NITROGEN = 6.25

# ============================================================================
# File Paths
# ============================================================================

SAVES_DIRECTORY = "saves"
LAST_PATH_FILE = "last_path.json"

# ============================================================================
# Application Metadata
# ============================================================================

APP_NAME = "Food Formulator"
APP_VERSION = "0.2.0"
APP_WINDOW_TITLE = "Food Formulator - Proto"

# Default window size
DEFAULT_WINDOW_WIDTH = 900
DEFAULT_WINDOW_HEIGHT = 600

# ============================================================================
# Nutrient Aliases
# ============================================================================

# Canonical mappings for nutrient name aliases
NUTRIENT_NAME_ALIASES = {
    "total sugars": "Sugars, Total",
    "sugars, total": "Sugars, Total",
    "cystine": "Cysteine",
    "cysteine": "Cysteine",
    "carbohydrate, by summation": "Carbohydrate, by difference",
    "carbohydrate by summation": "Carbohydrate, by difference",
    "choline, from phosphotidyl choline": "Choline, from phosphatidyl choline",
}

# Nutrient names to drop/ignore
NUTRIENT_NAMES_TO_DROP = {
    "energy (atwater general factors)",
    "energy (atwater specific factors)",
}

# ============================================================================
# Unit Normalization
# ============================================================================

# Microgram variants
MICROGRAM_VARIANTS = {"ug", "µg", "μg", "mcg"}
MICROGRAM_CANONICAL = "μg"

# ============================================================================
# Formulation Modes
# ============================================================================

QUANTITY_MODE_GRAMS = "g"
QUANTITY_MODE_PERCENT = "%"
