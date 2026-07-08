import logging
import os

logger = logging.getLogger()

database_password = os.environ.get("DATABASE_PASSWORD")
database_host = os.environ.get("DATABASE_HOST")
database_name = os.environ.get("DATABASE_NAME")
database_user = os.environ.get("DATABASE_USER")
admin_password = os.environ.get("ADMIN_PASSWORD")

FEATURE_FLAGS = {
    "ENABLE_TEMPLATE_PROCESSING": True,
    "DASHBOARD_CROSS_FILTERS": True,
    "DRILL_TO_DETAIL": True
}

ENABLE_PROXY_FIX = True

# SECRET_KEY — required in production; ephemeral fallback only in dev.
# Never ship a hardcoded/placeholder secret. Set SUPERSET_SECRET_KEY to a
# long, random, persistent value in production. In development
# (SUPERSET_ENV=development or DEV_MODE set), an ephemeral key is generated
# when unset so local dev still works (sessions won't survive a restart).
_superset_secret = os.environ.get('SUPERSET_SECRET_KEY')
if _superset_secret:
    SECRET_KEY = _superset_secret
elif os.environ.get('SUPERSET_ENV') == 'development' or os.environ.get('DEV_MODE'):
    import secrets as _secrets
    SECRET_KEY = _secrets.token_urlsafe(32)
    logger.warning(
        "SUPERSET_SECRET_KEY is unset in development mode; generated an "
        "ephemeral SECRET_KEY. Set SUPERSET_SECRET_KEY explicitly — session "
        "data will not survive a restart.")
else:
    raise RuntimeError(
        "SUPERSET_SECRET_KEY is required in production. Set it to a long, "
        "random, persistent value (do not commit it).")

# WTF_CSRF_ENABLED = False
TALISMAN_ENABLED = True

SQLALCHEMY_DATABASE_URI = f"postgresql+psycopg2://{database_user}:{database_password}@{database_host}:5432/{database_name}"
SQLALCHEMY_ECHO = True


# Flask-AppBuilder Init Hook for custom views
FLASK_APP_MUTATOR = lambda app: init_custom_views(app)

def init_custom_views(app):
    """Initialize custom views after Flask app is created"""
    try:
        from superset_chat.ai_superset_assistant import AISupersetAssistantView
        
        # Get the appbuilder instance
        from flask_appbuilder import AppBuilder
        appbuilder = app.appbuilder
        
        # Register the view
        appbuilder.add_view(
            AISupersetAssistantView,
            "AI Superset Assistant",
            icon="fa-robot",
            category="Custom Tools"
        )
        
        logger.info("✅ Functional AI Superset Assistant plugin registered successfully!")
        
    except Exception as e:
        logger.error(f"❌ Failed to register functional AI Superset Assistant plugin: {e}")
        import traceback
        logger.error(traceback.format_exc())
