from functools import wraps
from flask import abort
from flask_login import current_user


def role_required(role_name: str):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            # roles relationship may contain Role objects; compare by name
            user_roles = {r.name for r in getattr(current_user, 'roles', [])}
            if role_name not in user_roles:
                abort(403)
            return f(*args, **kwargs)
        return wrapped
    return decorator


def any_role_required(role_names: list[str]):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            user_roles = {r.name for r in getattr(current_user, 'roles', [])}
            if not set(role_names).intersection(user_roles):
                abort(403)
            return f(*args, **kwargs)
        return wrapped
    return decorator
