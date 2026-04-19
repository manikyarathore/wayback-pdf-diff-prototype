"""
Configuration and constants for the PDF diff pipeline.
All tunable parameters in one place for easy experimentation.
"""

import os
from pathlib import Path

# ============================================================================
# FILE PATHS
# ============================================================================
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = PROJECT_ROOT / "logs"

# Create directories if they don't exist
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)


# ============================================================================
# EXTRACTION SETTINGS
# ============================================================================
class ExtractionConfig:
    """Settings for PDF text extraction."""
    
    # Primary extraction library: "pymupdf" or "pdfminer"
    PRIMARY_EXTRACTOR = "pymupdf"
    
    # Fallback to alternative extractors on failure
    USE_FALLBACK = True
    FALLBACK_EXTRACTORS = ["pdfminer"]
    
    # Encryption handling
    ENCRYPTION_PASSWORD = ""  # Empty password attempt first
    SKIP_ENCRYPTED_ON_FAILURE = True
    
    # Processing limits
    MAX_PDF_SIZE_MB = 500
    PAGE_PROCESSING_TIMEOUT_SEC = 30
    
    # Quality thresholds
    MIN_CHARS_PER_PAGE_FOR_OCR_WARNING = 50  # Below this = likely scanned PDF


# ============================================================================
# STRUCTURE RECONSTRUCTION SETTINGS
# ============================================================================
class StructureConfig:
    """Settings for document structure reconstruction."""
    
    # Y-AXIS CLUSTERING (most critical parameter)
    Y_PROXIMITY_THRESHOLD_PX = 15  # Default: 15px
    Y_THRESHOLD_MIN = 8
    Y_THRESHOLD_MAX = 25
    Y_THRESHOLD_GRID_STEP = 2  # For threshold tuning
    
    # Adaptive threshold: scale based on font size
    ADAPTIVE_THRESHOLD_ENABLED = True
    ADAPTIVE_THRESHOLD_SCALE = 1.0  # Multiply font size by this
    
    # X-AXIS SORTING (left-to-right reading order within row)
    X_SORT_ENABLED = True
    
    # HORIZONTAL GAP THRESHOLD (space detection)
    HORIZONTAL_GAP_THRESHOLD_PX = 20
    
    # HEADING DETECTION
    HEADING_SIZE_THRESHOLD_PT = 14.0
    HEADING_REQUIRES_BOLD = True
    HEADING_SIZE_JUMP_THRESHOLD = 2.0  # Minimum pt size increase
    
    # MULTI-COLUMN DETECTION
    MULTI_COLUMN_DETECTION_ENABLED = True
    MIN_COLUMN_WIDTH = 100  # Minimum px for column
    
    # PARAGRAPH RECONSTRUCTION
    MIN_BLOCK_WIDTH_FOR_MERGE = 50  # Don't merge very narrow blocks
    MERGE_SHORT_BLOCKS = True
    SHORT_BLOCK_CHAR_LIMIT = 50


# ============================================================================
# NORMALIZATION SETTINGS
# ============================================================================
class NormalizationConfig:
    """Settings for text normalization."""
    
    # HEADER/FOOTER REMOVAL
    HEADER_FOOTER_PERCENTAGE = 5.0  # Remove top/bottom 5%
    ENABLE_HEADER_FOOTER_REMOVAL = True
    
    # WHITESPACE NORMALIZATION
    NORMALIZE_WHITESPACE = True
    NORMALIZE_NEWLINES = True
    
    # UNICODE NORMALIZATION
    UNICODE_NORMALIZATION_FORM = "NFC"  # NFC, NFKC, NFD, NFKD
    EXPAND_LIGATURES = True
    
    # LIGATURE MAPPING
    LIGATURES = {
        'ﬁ': 'fi',
        'ﬂ': 'fl',
        'ﬀ': 'ff',
        'ﬃ': 'ffi',
        'ﬄ': 'ffl',
        'ﬅ': 'ft',
        'ﬆ': 'st',
    }
    
    # PAGE NUMBER REMOVAL
    REMOVE_PAGE_NUMBERS = True
    PAGE_NUMBER_PATTERNS = [
        r'^\d+$',  # Standalone number
        r'^Page \d+',  # "Page N"
        r'^\d+ of \d+$',  # "N of M"
        r'^- \d+ -$',  # "- N -"
    ]
    
    # FONT METADATA SCRUBBING
    SCRUB_FONT_METADATA = True  # Ignore font changes in similarity


# ============================================================================
# DIFF ENGINE SETTINGS
# ============================================================================
class DiffConfig:
    """Settings for multi-level diffing."""
    
    # BLOCK-LEVEL ALIGNMENT
    BLOCK_SIMILARITY_THRESHOLD = 0.75  # Match threshold
    CHAR_MATCH_WEIGHT = 0.7  # Text similarity weight
    LAYOUT_PROXIMITY_WEIGHT = 0.3  # Layout similarity weight
    
    # SENTENCE TOKENIZATION
    ABBREVIATIONS = {
        'Mr', 'Mrs', 'Ms', 'Dr', 'Prof', 'Inc', 'Ltd', 'Co',
        'etc', 'vs', 'viz', 'e.g', 'i.e', 'a.m', 'p.m',
        'U.S', 'U.K', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
        'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'
    }
    
    # CONFIDENCE SCORING COMPONENTS
    CONFIDENCE_BLOCK_SIMILARITY_WEIGHT = 0.35
    CONFIDENCE_TEXT_MATCH_WEIGHT = 0.35
    CONFIDENCE_LAYOUT_CONSISTENCY_WEIGHT = 0.20
    CONFIDENCE_CONTEXT_CONSISTENCY_WEIGHT = 0.10
    
    # CONTEXT LINES
    CONTEXT_SENTENCES_BEFORE = 2
    CONTEXT_SENTENCES_AFTER = 2
    
    # LAYOUT CONSISTENCY (detect major position shifts)
    MAX_POSITION_DELTA_FOR_CONSISTENCY = 0.20  # 20% of page


# ============================================================================
# LOGGING SETTINGS
# ============================================================================
class LoggingConfig:
    """Settings for logging."""
    
    LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    LOG_FILE = LOGS_DIR / "pdf_diff.log"
    LOG_FORMAT = (
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    STRUCTURED_JSON_LOGS = True  # Log as JSON for easy parsing


# ============================================================================
# PERFORMANCE SETTINGS
# ============================================================================
class PerformanceConfig:
    """Settings for performance optimization."""
    
    # CHUNKING FOR LARGE PDFS
    PAGE_CHUNK_SIZE = 50  # Process 50 pages at a time
    ENABLE_CHUNKING = True
    
    # CACHING
    ENABLE_CACHING = False  # Not in prototype phase
    CACHE_TTL_HOURS = 24
    
    # PERFORMANCE TARGETS
    TARGET_PROCESSING_TIME_MS = 2000  # 2 seconds for 100-page PDF
    PROFILING_ENABLED = False


# ============================================================================
# TESTING & VALIDATION
# ============================================================================
class TestingConfig:
    """Settings for testing and validation."""
    
    # TEST CORPUS
    TEST_CORPUS_DIR = DATA_DIR / "test_corpus"
    EXPECTED_RESULTS_DIR = DATA_DIR / "expected_results"
    
    # EVALUATION METRICS TARGETS
    TARGET_PARAGRAPH_F1_SCORE = 0.85
    TARGET_DIFF_ACCURACY = 0.90
    TARGET_FALSE_POSITIVE_RATE = 0.05  # 5% max
    
    # SAMPLE SIZES
    MANUAL_REVIEW_SAMPLE_SIZE = 50  # Review 50 borderline changes
    EDGE_CASE_TEST_COUNT = 20


# ============================================================================
# THRESHOLDS FOR HEURISTICS
# ============================================================================
class HeuristicsConfig:
    """Settings for heuristic-based decisions."""
    
    # FORMATTING VS. CONTENT CHANGES
    FONT_SIZE_DELTA_THRESHOLD = 2.0  # Ignore font changes < 2pt
    COLOR_DELTA_THRESHOLD = 30  # Ignore color changes < 30 in RGB distance
    POSITION_DELTA_THRESHOLD_PX = 5  # Ignore position changes < 5px
    
    # SCANNED PDF DETECTION
    SCANNED_PDF_CHAR_THRESHOLD = 50  # < this chars per page = scanned
    
    # SPECIAL BLOCK DETECTION
    IS_BULLET_POINT = lambda text: text.strip().startswith(('•', '◦', '▪', '-', '*', '+'))
    IS_QUOTE = lambda text: text.strip().startswith('"') or text.strip().startswith("'")
    IS_URL = lambda text: 'http' in text.lower() or 'www' in text.lower()


# ============================================================================
# QUALITY ASSURANCE
# ============================================================================
class QAConfig:
    """Settings for quality assurance."""
    
    # UNIT TEST COVERAGE TARGET
    MIN_LINE_COVERAGE = 0.85  # 85% minimum
    MIN_BRANCH_COVERAGE = 0.70  # 70% minimum
    
    # INTEGRATION TEST EXPECTATIONS
    INTEGRATION_TEST_CORPUS_SIZE = 50
    INTEGRATION_TEST_TIMEOUT_SEC = 60
    
    # REGRESSION TESTING
    PERFORMANCE_REGRESSION_THRESHOLD = 0.20  # Fail if >20% slower
    ACCURACY_REGRESSION_THRESHOLD = 0.05  # Fail if accuracy drops >5%


# ============================================================================
# EXPORT & OUTPUT
# ============================================================================
class OutputConfig:
    """Settings for output formats."""
    
    # OUTPUT FORMATS
    SUPPORT_JSON = True
    SUPPORT_HTML = True
    SUPPORT_MARKDOWN = True
    SUPPORT_CSV = False  # Phase 2
    
    # DEFAULT CONFIDENCE FILTER
    DEFAULT_MIN_CONFIDENCE = 60  # 0-100
    
    # HTML OUTPUT STYLING
    HIGHLIGHT_ADDED_COLOR = "#d4edda"  # Green
    HIGHLIGHT_DELETED_COLOR = "#f8d7da"  # Red
    HIGHLIGHT_MODIFIED_COLOR = "#fff3cd"  # Yellow
    HIGHLIGHT_TEXT_COLOR_ADDED = "#155724"
    HIGHLIGHT_TEXT_COLOR_DELETED = "#721c24"
    HIGHLIGHT_TEXT_COLOR_MODIFIED = "#856404"


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================
def get_all_configs() -> dict:
    """Get all configuration classes."""
    return {
        'extraction': ExtractionConfig,
        'structure': StructureConfig,
        'normalization': NormalizationConfig,
        'diff': DiffConfig,
        'logging': LoggingConfig,
        'performance': PerformanceConfig,
        'testing': TestingConfig,
        'heuristics': HeuristicsConfig,
        'qa': QAConfig,
        'output': OutputConfig,
    }


def print_config():
    """Print all configuration values for debugging."""
    import json
    
    configs = get_all_configs()
    all_config = {}
    
    for config_name, config_class in configs.items():
        all_config[config_name] = {
            k: v for k, v in vars(config_class).items()
            if not k.startswith('_')
        }
    
    print(json.dumps(all_config, indent=2, default=str))
