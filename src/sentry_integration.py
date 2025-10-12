"""
Sentry Integration for Production Error Tracking

Автоматически отслеживает:
- Все uncaught exceptions
- HTTP errors (4xx, 5xx)
- Performance issues
- Database query performance
- Background task errors
"""

import os
import logging

logger = logging.getLogger(__name__)

def init_sentry():
    """
    Инициализирует Sentry SDK для error tracking.
    
    Требует переменную окружения SENTRY_DSN.
    """
    sentry_dsn = os.getenv("SENTRY_DSN")
    
    if not sentry_dsn:
        logger.info("[sentry] SENTRY_DSN not set, error tracking disabled")
        return False
    
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration
        
        # Настройка logging integration
        logging_integration = LoggingIntegration(
            level=logging.INFO,        # Capture info and above as breadcrumbs
            event_level=logging.ERROR  # Send errors as events
        )
        
        sentry_sdk.init(
            dsn=sentry_dsn,
            environment=os.getenv("ENVIRONMENT", "production"),
            
            # Performance Monitoring
            traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),  # 10% requests
            profiles_sample_rate=float(os.getenv("SENTRY_PROFILES_SAMPLE_RATE", "0.1")),  # 10% profiles
            
            # Integrations
            integrations=[
                FastApiIntegration(),
                SqlalchemyIntegration(),
                logging_integration,
            ],
            
            # Ignore expected errors
            ignore_errors=[
                KeyboardInterrupt,
                SystemExit,
            ],
            
            # Release tracking для версионирования
            release=os.getenv("RELEASE_VERSION", "unknown"),
            
            # Tags для фильтрации в Sentry UI
            tags={
                "service": "myassistent",
                "component": "trading-bot",
            },
            
            # Before send hook для фильтрации sensitive data
            before_send=before_send_filter,
            
            # Max breadcrumbs
            max_breadcrumbs=50,
            
            # Attach stacktrace to messages
            attach_stacktrace=True,
        )
        
        environment = os.getenv("ENVIRONMENT", "production")
        release = os.getenv("RELEASE_VERSION", "unknown")
        logger.info(f"[sentry] Initialized successfully (env={environment}, release={release})")
        
        return True
        
    except ImportError:
        logger.warning("[sentry] sentry-sdk not installed, run: pip install sentry-sdk[fastapi]")
        return False
    
    except Exception as e:
        logger.error(f"[sentry] Failed to initialize: {e}")
        return False


def before_send_filter(event, hint):
    """
    Фильтр для sensitive data перед отправкой в Sentry.
    
    Удаляет:
    - API keys
    - Passwords
    - Tokens
    - Private keys
    """
    # Список sensitive ключей для фильтрации
    sensitive_keys = [
        'api_key', 'apikey', 'api-key',
        'password', 'passwd', 'pwd',
        'secret', 'token', 'auth',
        'private_key', 'privatekey',
        'bybit_api_key', 'bybit_api_secret',
        'telegram_bot_token',
    ]
    
    def filter_dict(d):
        """Рекурсивно фильтрует словарь"""
        if not isinstance(d, dict):
            return d
        
        filtered = {}
        for key, value in d.items():
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                filtered[key] = "[FILTERED]"
            elif isinstance(value, dict):
                filtered[key] = filter_dict(value)
            elif isinstance(value, list):
                filtered[key] = [filter_dict(item) if isinstance(item, dict) else item for item in value]
            else:
                filtered[key] = value
        
        return filtered
    
    # Фильтрация request data
    if 'request' in event:
        if 'data' in event['request']:
            event['request']['data'] = filter_dict(event['request']['data'])
        if 'headers' in event['request']:
            event['request']['headers'] = filter_dict(event['request']['headers'])
    
    # Фильтрация extra data
    if 'extra' in event:
        event['extra'] = filter_dict(event['extra'])
    
    return event


def capture_exception(error: Exception, context: dict = None):
    """
    Захватить exception вручную и отправить в Sentry.
    
    Args:
        error: Exception для отправки
        context: Дополнительный контекст (dict)
    
    Example:
        try:
            risky_operation()
        except Exception as e:
            capture_exception(e, {"user_id": 123, "action": "trade"})
    """
    try:
        import sentry_sdk
        
        if context:
            with sentry_sdk.push_scope() as scope:
                for key, value in context.items():
                    scope.set_extra(key, value)
                sentry_sdk.capture_exception(error)
        else:
            sentry_sdk.capture_exception(error)
    
    except Exception as e:
        logger.error(f"[sentry] Failed to capture exception: {e}")


def capture_message(message: str, level: str = "info", context: dict = None):
    """
    Отправить message в Sentry.
    
    Args:
        message: Сообщение
        level: Уровень (debug, info, warning, error, fatal)
        context: Дополнительный контекст
    
    Example:
        capture_message("Trade executed successfully", "info", {"symbol": "BTC/USDT"})
    """
    try:
        import sentry_sdk
        
        if context:
            with sentry_sdk.push_scope() as scope:
                for key, value in context.items():
                    scope.set_extra(key, value)
                sentry_sdk.capture_message(message, level=level)
        else:
            sentry_sdk.capture_message(message, level=level)
    
    except Exception as e:
        logger.error(f"[sentry] Failed to capture message: {e}")


def set_user_context(user_id: str = None, email: str = None, **kwargs):
    """
    Установить user context для Sentry events.
    
    Args:
        user_id: ID пользователя
        email: Email пользователя
        **kwargs: Дополнительные поля
    """
    try:
        import sentry_sdk
        
        user_data = {}
        if user_id:
            user_data["id"] = user_id
        if email:
            user_data["email"] = email
        
        user_data.update(kwargs)
        
        sentry_sdk.set_user(user_data)
    
    except Exception as e:
        logger.error(f"[sentry] Failed to set user context: {e}")


def add_breadcrumb(message: str, category: str = "default", level: str = "info", data: dict = None):
    """
    Добавить breadcrumb для контекста ошибки.
    
    Args:
        message: Описание действия
        category: Категория (navigation, http, db, etc.)
        level: Уровень (debug, info, warning, error)
        data: Дополнительные данные
    
    Example:
        add_breadcrumb("Fetching prices from Bybit", "api", "info", {"symbol": "BTC/USDT"})
    """
    try:
        import sentry_sdk
        
        sentry_sdk.add_breadcrumb(
            message=message,
            category=category,
            level=level,
            data=data or {}
        )
    
    except Exception as e:
        logger.error(f"[sentry] Failed to add breadcrumb: {e}")

