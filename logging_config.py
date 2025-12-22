"""
Centralized Logging Configuration for Friktionskompasset
Provides structured logging with JSON formatting and log rotation
"""
import logging
import logging.handlers
import os
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any


# Log levels mapping
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()

# Determine log directory based on environment
RENDER_DISK_PATH = "/var/data"
if os.path.exists(RENDER_DISK_PATH):
    # Production on Render
    LOG_DIR = os.path.join(RENDER_DISK_PATH, 'logs')
else:
    # Local development
    LOG_DIR = os.path.join(os.path.dirname(__file__), 'logs')

# Ensure log directory exists
Path(LOG_DIR).mkdir(parents=True, exist_ok=True)

# Log file paths
APP_LOG_FILE = os.path.join(LOG_DIR, 'app.log')
ERROR_LOG_FILE = os.path.join(LOG_DIR, 'error.log')
SECURITY_LOG_FILE = os.path.join(LOG_DIR, 'security.log')


class JSONFormatter(logging.Formatter):
    """
    Custom JSON formatter for structured logging.
    Outputs logs as JSON objects for easier parsing and analysis.
    """

    # Sensitive fields that should not be logged
    SENSITIVE_FIELDS = {
        'password', 'password_hash', 'token', 'secret', 'api_key',
        'access_token', 'refresh_token', 'authorization', 'cookie',
        'session_id', 'csrf_token'
    }

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON"""
        log_data = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'message': record.getMessage(),
        }

        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)

        # Add extra fields if present (from logger.info('msg', extra={...}))
        if hasattr(record, 'extra_data'):
            log_data['extra'] = self._sanitize_data(record.extra_data)

        # Add request context if available
        try:
            from flask import has_request_context, request
            if has_request_context():
                log_data['request'] = {
                    'method': request.method,
                    'path': request.path,
                    'remote_addr': request.remote_addr,
                    'user_agent': request.headers.get('User-Agent', ''),
                }
                # Add user info if available in session
                if hasattr(request, 'user_id'):
                    log_data['request']['user_id'] = request.user_id
        except (ImportError, RuntimeError):
            # Flask not available or no request context
            pass

        return json.dumps(log_data, default=str)

    def _sanitize_data(self, data: Any) -> Any:
        """Remove sensitive information from log data"""
        if isinstance(data, dict):
            return {
                key: '***REDACTED***' if key.lower() in self.SENSITIVE_FIELDS else self._sanitize_data(value)
                for key, value in data.items()
            }
        elif isinstance(data, (list, tuple)):
            return [self._sanitize_data(item) for item in data]
        else:
            return data


class ColoredConsoleFormatter(logging.Formatter):
    """
    Colored console formatter for better readability in development.
    """

    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
    }
    RESET = '\033[0m'

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors"""
        color = self.COLORS.get(record.levelname, self.RESET)

        # Format: [TIMESTAMP] LEVEL [module.function] message
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        level = f"{color}{record.levelname:8}{self.RESET}"
        location = f"{record.module}.{record.funcName}"
        message = record.getMessage()

        log_line = f"[{timestamp}] {level} [{location}] {message}"

        # Add exception traceback if present
        if record.exc_info:
            log_line += '\n' + self.formatException(record.exc_info)

        return log_line


def setup_logging(app_name: str = 'friktionskompasset') -> logging.Logger:
    """
    Setup centralized logging configuration.

    Args:
        app_name: Name of the application logger

    Returns:
        Configured root logger
    """
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(LOG_LEVEL)

    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()

    # 1. Console Handler (for development and stdout in production)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(LOG_LEVEL)

    # Use colored formatter for local development, JSON for production
    if os.path.exists(RENDER_DISK_PATH):
        # Production: JSON format
        console_handler.setFormatter(JSONFormatter())
    else:
        # Development: Colored format
        console_handler.setFormatter(ColoredConsoleFormatter())

    root_logger.addHandler(console_handler)

    # 2. App Log File Handler (all logs)
    try:
        app_file_handler = logging.handlers.RotatingFileHandler(
            APP_LOG_FILE,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding='utf-8'
        )
        app_file_handler.setLevel(logging.DEBUG)
        app_file_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(app_file_handler)
    except Exception as e:
        print(f"Warning: Could not setup app log file handler: {e}", file=sys.stderr)

    # 3. Error Log File Handler (ERROR and CRITICAL only)
    try:
        error_file_handler = logging.handlers.RotatingFileHandler(
            ERROR_LOG_FILE,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding='utf-8'
        )
        error_file_handler.setLevel(logging.ERROR)
        error_file_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(error_file_handler)
    except Exception as e:
        print(f"Warning: Could not setup error log file handler: {e}", file=sys.stderr)

    # 4. Security Log File Handler (custom level)
    try:
        security_file_handler = logging.handlers.RotatingFileHandler(
            SECURITY_LOG_FILE,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=10,  # Keep more security logs
            encoding='utf-8'
        )
        security_file_handler.setLevel(logging.WARNING)
        security_file_handler.setFormatter(JSONFormatter())

        # Add filter to only log security-related events
        security_file_handler.addFilter(SecurityLogFilter())
        root_logger.addHandler(security_file_handler)
    except Exception as e:
        print(f"Warning: Could not setup security log file handler: {e}", file=sys.stderr)

    # Configure third-party loggers to be less verbose
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('authlib').setLevel(logging.WARNING)

    # Log startup message
    logger = logging.getLogger(app_name)
    logger.info(f"Logging configured", extra={'extra_data': {
        'log_level': LOG_LEVEL,
        'log_dir': LOG_DIR,
        'environment': 'production' if os.path.exists(RENDER_DISK_PATH) else 'development'
    }})

    return root_logger


class SecurityLogFilter(logging.Filter):
    """
    Filter to identify security-related log events.
    Logs from security module or containing security keywords.
    """

    SECURITY_KEYWORDS = {
        'login', 'logout', 'authentication', 'authorization',
        'permission', 'access denied', 'unauthorized', 'forbidden',
        'injection', 'xss', 'csrf', 'sql', 'security', 'breach',
        'suspicious', 'attack', 'malicious', 'exploit'
    }

    def filter(self, record: logging.LogRecord) -> bool:
        """Return True if record is security-related"""
        # Check if from security module
        if 'security' in record.name.lower() or 'auth' in record.name.lower():
            return True

        # Check message for security keywords
        message = record.getMessage().lower()
        return any(keyword in message for keyword in self.SECURITY_KEYWORDS)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the given name.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


def log_security_event(logger: logging.Logger, event_type: str, details: Dict[str, Any]):
    """
    Log a security event with structured data.

    Args:
        logger: Logger instance
        event_type: Type of security event (e.g., 'login_failed', 'access_denied')
        details: Event details dictionary
    """
    logger.warning(
        f"Security event: {event_type}",
        extra={'extra_data': {'event_type': event_type, **details}}
    )


def log_request(logger: logging.Logger, request, response_code: int, duration_ms: float):
    """
    Log HTTP request with details.

    Args:
        logger: Logger instance
        request: Flask request object
        response_code: HTTP response code
        duration_ms: Request duration in milliseconds
    """
    logger.info(
        f"{request.method} {request.path} {response_code}",
        extra={'extra_data': {
            'method': request.method,
            'path': request.path,
            'status_code': response_code,
            'duration_ms': duration_ms,
            'remote_addr': request.remote_addr,
            'user_agent': request.headers.get('User-Agent', ''),
        }}
    )


# Initialize logging on module import
setup_logging()
