"""
Application configuration settings.
In production, these should be loaded from environment variables.
"""

import os

# JWT Settings
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production-please")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15  # Short-lived access tokens
REFRESH_TOKEN_EXPIRE_DAYS = 7    # Long-lived refresh tokens

# File Upload Settings
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB limit
