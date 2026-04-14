# codeeditor/config.py
# Central configuration — constants, paths, default settings.

from pathlib import Path

APP_NAME = "CodeEditor"
APP_VERSION = "2.0.0"
WINDOW_TITLE = f"{APP_NAME} v{APP_VERSION}"

# Default window geometry
DEFAULT_WIDTH = 1400
DEFAULT_HEIGHT = 820

# Editor defaults
DEFAULT_FONT_SIZE = 11
DEFAULT_TAB_WIDTH = 4

# Supported file extensions for syntax highlighting
PYTHON_EXTENSIONS = {".py", ".pyw", ".pyi"}
JAVASCRIPT_EXTENSIONS = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
ALL_CODE_EXTENSIONS = PYTHON_EXTENSIONS | JAVASCRIPT_EXTENSIONS

# File filters for tree view
CODE_FILE_FILTERS = [
    "*.py", "*.pyw", "*.pyi",
    "*.js", "*.jsx", "*.ts", "*.tsx",
    "*.json", "*.md", "*.txt", "*.html", "*.css",
    "*.yaml", "*.yml", "*.toml", "*.cfg", "*.ini",
]

# GIF engine state categories (expandable)
GIF_CATEGORIES = [
    "idle",
    "saving",
    "typing",
    "ai_waiting",
    "ai_response",
    "error",
]

# GIF engine priorities — higher number = higher priority
GIF_PRIORITY = {
    "idle": 0,
    "typing": 1,
    "saving": 2,
    "ai_response": 3,
    "ai_waiting": 4,
    "error": 5,
}

# Idle timeout in milliseconds (how long before "idle" gifs kick in)
IDLE_TIMEOUT_MS = 30_000  # 30 seconds

# Asset / GIF paths
ASSETS_DIR = Path(__file__).parent / "assets"
GIF_BASE_DIR = ASSETS_DIR / "gifs"

# GIF engine timing
GIF_ROTATION_INTERVAL_MS = 8000   # rotate to next GIF in same folder
GIF_TYPING_DEBOUNCE_MS = 2000     # clear "typing" state after no keystrokes
GIF_SAVING_DURATION_MS = 3000     # how long "saving" state persists

# Snapshot folder name
SNAPSHOT_DIR_NAME = ".history"

# Config file location
CONFIG_DIR = Path.home() / ".codeeditor"
CONFIG_FILE = CONFIG_DIR / "config.json"

# Session log directory
SESSION_LOG_DIR = CONFIG_DIR / "sessions"

# AI defaults
DEFAULT_GEMINI_MODEL = "gemini-3.1-flash-lite-preview"
DEFAULT_GPT_MODEL = "gpt-5.4-mini"
DEFAULT_CLAUDE_MODEL = "claude-sonnet-4-6"
GEMINI_API_KEY_ENV = "GEMINI_API_KEY"
OPENAI_API_KEY_ENV = "OPENAI_API_KEY"
ANTHROPIC_API_KEY_ENV = "ANTHROPIC_API_KEY"
MAX_ATTACHMENT_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
AI_RESPONSE_GIF_DURATION_MS = 3000

# Auto-save
AUTO_SAVE_INTERVAL_MS = 60_000  # 1 minute

# Supported media extensions for the GIF/video engine
MEDIA_EXTENSIONS = {".gif", ".mp4"}

# One-shot reaction categories (play once, revert to previous state)
GIF_REACTION_CATEGORIES = [
    "initial",
    "opening",
    "pressing_backspace",
    "selected_claude",
    "selected_gpt",
    "selected_gemini",
    "light_mode_enabled",
    "dark_mode_enabled",
    "pasting",
    "returned",
    "easter_eggs",
    "auto_save",
    "no_search_results",
    "mute",
]

# Reaction timing
REACTION_DEBOUNCE_MS = 1500            # debounce for rapid-fire reactions
RETURNED_THRESHOLD_S = 180             # 3 minutes away → "returned" reaction
EASTER_EGG_MIN_INTERVAL_MS = 600_000   # 10 minutes minimum between easter eggs
EASTER_EGG_MAX_INTERVAL_MS = 1_800_000 # 30 minutes maximum
REACTION_SAFETY_TIMEOUT_MS = 10_000    # max clip duration before forced revert

# Minimap
DEFAULT_MINIMAP_WIDTH = 80
MINIMAP_RENDER_DEBOUNCE_MS = 100

# Recent files
MAX_RECENT_FILES = 10
