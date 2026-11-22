"""Constantes globales de l'application LogWaver.

Toutes les valeurs « magiques » (noms de champs, formats de fichiers,
identifiants de catégories spéciales...) sont centralisées ici afin d'éviter
toute duplication dans le code.
"""

from __future__ import annotations

APP_NAME: str = "LogWaver"
APP_ORGANIZATION: str = "LogWaver"

# --- Champs standards extraits par les plugins --------------------------------
FIELD_FILE: str = "file"
FIELD_LINE: str = "line"
FIELD_CODE: str = "code"
FIELD_DESCRIPTION: str = "description"
STANDARD_FIELDS: tuple = (FIELD_FILE, FIELD_LINE, FIELD_CODE, FIELD_DESCRIPTION)

FIELD_LABELS: dict = {
    FIELD_FILE: "Fichier",
    FIELD_LINE: "Ligne",
    FIELD_CODE: "Code",
    FIELD_DESCRIPTION: "Description",
}

# --- Clés utilisables pour l'empreinte (fingerprint) d'un élément -------------
MATCH_KEY_TOOL: str = "tool"
MATCH_KEY_TYPE: str = "type"
MATCH_KEY_CODE: str = "code"
MATCH_KEY_DESCRIPTION: str = "description"
MATCH_KEY_FILE_NAME: str = "file_name"
MATCH_KEY_FILE_PATH: str = "file_path"
MATCH_KEY_LINE: str = "line"
ALLOWED_MATCH_KEYS: tuple = (
    MATCH_KEY_TOOL,
    MATCH_KEY_TYPE,
    MATCH_KEY_CODE,
    MATCH_KEY_DESCRIPTION,
    MATCH_KEY_FILE_NAME,
    MATCH_KEY_FILE_PATH,
    MATCH_KEY_LINE,
)
DEFAULT_MATCH_KEYS: tuple = (
    MATCH_KEY_TOOL,
    MATCH_KEY_TYPE,
    MATCH_KEY_CODE,
    MATCH_KEY_DESCRIPTION,
    MATCH_KEY_FILE_NAME,
)

# --- Catégories spéciales de la vue ------------------------------------------
CATEGORY_ALL: str = "__all__"
CATEGORY_UNCLASSIFIED: str = "__unclassified__"
CATEGORY_ALL_LABEL: str = "Tous les éléments"
CATEGORY_UNCLASSIFIED_LABEL: str = "Non justifiés (sans classe)"

# --- Origine d'une justification ---------------------------------------------
SOURCE_MANUAL: str = "manuelle"
SOURCE_AI: str = "ia"
SOURCE_IMPORTED: str = "importée"

# --- Formats de fichiers ------------------------------------------------------
PROJECT_FORMAT_NAME: str = "logwaver-project"
RULES_FORMAT_NAME: str = "logwaver-justifications"
FILE_FORMAT_VERSION: int = 2  # v2 : règles de correspondance enregistrées
PROJECT_FILE_EXTENSION: str = ".lwp"
RULES_FILE_EXTENSION: str = ".lwj"
PLUGIN_FILE_EXTENSION: str = ".ini"
FILE_ENCODING: str = "utf-8"
LOG_FALLBACK_ENCODING: str = "latin-1"

# --- Sections des fichiers INI -------------------------------------------------
PLUGIN_SECTION: str = "plugin"
PLUGIN_TYPE_SECTION_PREFIX: str = "type:"
PLUGIN_REGEX_KEY_PREFIX: str = "regex."
PDF_INDEX_SECTION: str = "pages"
CONFIG_STATUS_SECTION_PREFIX: str = "status:"

# --- Divers -------------------------------------------------------------------
FINGERPRINT_SEPARATOR: str = "␟"  # caractère « unit separator » visible
FINGERPRINT_HASH_LENGTH: int = 20
DEFAULT_AI_LANGUAGE: str = "fr"
LOG_DIRECTORY_NAME: str = ".logwaver"
LOG_FILE_NAME: str = "logwaver.log"
