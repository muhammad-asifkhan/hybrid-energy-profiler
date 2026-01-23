"""
auth.py: Authentication and authorization system for Hybrid Energy Profiler.

Provides:
- User authentication (login/logout)
- Role-based access control (viewer, admin)
- Session management
- Password hashing
"""
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from functools import wraps
from flask import session, request, abort, redirect, url_for
from energymon.config import get_config
from energymon.logger import get_logger
from energymon.storage import get_storage

config = get_config()
logger = get_logger('energymon.auth')

# Simple in-memory user store (can be upgraded to database)
_users: Dict[str, Dict[str, Any]] = {}

# Default users (should be changed in production)
DEFAULT_USERS = {
    'admin': {
        'password_hash': None,  # Will be set on first use
        'role': 'admin',
        'created': datetime.now()
    },
    'viewer': {
        'password_hash': None,
        'role': 'viewer',
        'created': datetime.now()
    }
}


def hash_password(password: str) -> str:
    """
    Hash password using SHA-256 with salt.
    
    Args:
        password: Plain text password
    
    Returns:
        Hashed password string
    """
    salt = secrets.token_hex(16)
    password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"{salt}:{password_hash}"


def verify_password(password: str, password_hash: str) -> bool:
    """
    Verify password against hash.
    
    Args:
        password: Plain text password
        password_hash: Stored password hash
    
    Returns:
        True if password matches
    """
    if not password_hash or ':' not in password_hash:
        return False
    
    salt, stored_hash = password_hash.split(':', 1)
    computed_hash = hashlib.sha256((password + salt).encode()).hexdigest()
    return computed_hash == stored_hash


def init_users() -> None:
    """Initialize default users if not exists."""
    global _users
    
    # Load from config or use defaults
    users_config = config.get('security', 'users', default={})
    
    if not users_config:
        # Use default users with default passwords
        _users = {
            'admin': {
                'password_hash': hash_password('admin123'),  # CHANGE IN PRODUCTION!
                'role': 'admin',
                'created': datetime.now()
            },
            'viewer': {
                'password_hash': hash_password('viewer123'),  # CHANGE IN PRODUCTION!
                'role': 'viewer',
                'created': datetime.now()
            }
        }
        logger.warning("Using default users! Change passwords in production!")
    else:
        # Load from config
        for username, user_data in users_config.items():
            _users[username] = {
                'password_hash': user_data.get('password_hash'),
                'role': user_data.get('role', 'viewer'),
                'created': datetime.now()
            }
    
    logger.info(f"Initialized {len(_users)} users")


def authenticate(username: str, password: str) -> bool:
    """
    Authenticate user.
    
    Args:
        username: Username
        password: Password
    
    Returns:
        True if authentication successful
    """
    if not _users:
        init_users()
    
    if username not in _users:
        logger.warning(f"Authentication failed: user '{username}' not found")
        return False
    
    user = _users[username]
    if verify_password(password, user['password_hash']):
        logger.info(f"User '{username}' authenticated successfully")
        return True
    else:
        logger.warning(f"Authentication failed: invalid password for '{username}'")
        return False


def login_user(username: str) -> None:
    """
    Log in user (create session).
    
    Args:
        username: Username
    """
    session['username'] = username
    session['role'] = _users[username]['role']
    session['logged_in'] = True
    session.permanent = True
    logger.info(f"User '{username}' logged in")


def logout_user() -> None:
    """Log out current user."""
    username = session.get('username', 'unknown')
    session.clear()
    logger.info(f"User '{username}' logged out")


def get_current_user() -> Optional[Dict[str, Any]]:
    """
    Get current logged-in user.
    
    Returns:
        User dict or None if not logged in
    """
    if not session.get('logged_in'):
        return None
    
    username = session.get('username')
    if username and username in _users:
        return {
            'username': username,
            'role': session.get('role', 'viewer')
        }
    return None


def require_login(f):
    """Decorator to require login."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if auth is required
        from energymon.config import get_config
        config = get_config()
        require_auth = config.get('security', 'require_auth', default=False)
        
        # Skip auth check if not required
        if not require_auth:
            return f(*args, **kwargs)
        
        # Check if user is logged in
        if not session.get('logged_in'):
            if request.is_json or request.path.startswith('/api/'):
                abort(401)
            # Use direct redirect to avoid url_for issues
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated_function


def require_role(role: str):
    """
    Decorator to require specific role.
    
    Args:
        role: Required role ('viewer' or 'admin')
    """
    def decorator(f):
        @wraps(f)
        @require_login
        def decorated_function(*args, **kwargs):
            user = get_current_user()
            if not user:
                abort(401)
            
            user_role = user.get('role', 'viewer')
            if user_role != role and user_role != 'admin':
                logger.warning(f"Access denied: user '{user['username']}' (role: {user_role}) tried to access {request.path}")
                abort(403)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def is_authenticated() -> bool:
    """Check if user is authenticated."""
    return session.get('logged_in', False)


def has_role(role: str) -> bool:
    """
    Check if current user has specific role.
    
    Args:
        role: Role to check
    
    Returns:
        True if user has role or is admin
    """
    user = get_current_user()
    if not user:
        return False
    
    user_role = user.get('role', 'viewer')
    return user_role == role or user_role == 'admin'


# Initialize users on module load
init_users()
