"""core/security.py - security helpers live here.

In a real app this holds password hashing and JWT creation/validation
(Lesson 29). Kept minimal here to show WHERE security code belongs in the
structure, not to re-teach auth.
"""

import hashlib


def hash_secret(value: str) -> str:
    # Placeholder only. Real apps use bcrypt (Lesson 29), never a bare hash.
    return hashlib.sha256(value.encode()).hexdigest()
