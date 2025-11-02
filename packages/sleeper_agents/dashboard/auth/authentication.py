"""
Authentication system for the dashboard.
Simple username/password system with SQLite backend.
"""

import logging
import sqlite3
from pathlib import Path
from typing import Dict, Optional

import bcrypt

logger = logging.getLogger(__name__)


class AuthManager:
    """Manages user authentication for the dashboard."""

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize authentication manager.

        Args:
            db_path: Path to user database. Defaults to auth/users.db
        """
        if db_path is None:
            db_path = Path(__file__).parent / "users.db"

        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self._init_database()

        # Create default admin user if no users exist
        self._create_default_admin()

    def _init_database(self):
        """Initialize the user database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                is_admin BOOLEAN DEFAULT 0
            )
        """
        )

        conn.commit()
        conn.close()

    def _create_default_admin(self):
        """Create default admin user if no users exist."""
        import os
        import secrets
        import string

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]

        if user_count == 0:
            # Check for environment variable or generate random password
            default_password = os.environ.get("DASHBOARD_ADMIN_PASSWORD")

            if not default_password:
                # Generate a secure random password
                alphabet = string.ascii_letters + string.digits + "!@#$%"
                default_password = "".join(secrets.choice(alphabet) for _ in range(16))

            hashed = bcrypt.hashpw(default_password.encode("utf-8"), bcrypt.gensalt())

            cursor.execute(
                """
                INSERT INTO users (username, password_hash, is_admin)
                VALUES (?, ?, ?)
            """,
                ("admin", hashed, True),
            )

            conn.commit()

            # Log the credentials securely
            logger.info("Created default admin user")
            print("\n" + "=" * 60)
            print("[PIN] DASHBOARD ADMIN CREDENTIALS CREATED")
            print("=" * 60)
            print("Username: admin")
            print(f"Password: {default_password}")
            print("\n[WARNING]  IMPORTANT: Save this password! It will not be shown again.")
            print("   To set your own password, restart with DASHBOARD_ADMIN_PASSWORD env variable")
            print("=" * 60 + "\n")

        conn.close()

    def authenticate(self, username: str, password: str) -> bool:
        """Authenticate a user.

        Args:
            username: Username to authenticate
            password: Password to verify

        Returns:
            True if authentication successful, False otherwise
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT password_hash FROM users WHERE username = ?
        """,
            (username,),
        )

        result = cursor.fetchone()

        if result is None:
            conn.close()
            return False

        password_hash = result[0]

        # Verify password
        is_valid = bcrypt.checkpw(password.encode("utf-8"), password_hash)

        if is_valid:
            # Update last login time
            cursor.execute(
                """
                UPDATE users SET last_login = CURRENT_TIMESTAMP
                WHERE username = ?
            """,
                (username,),
            )
            conn.commit()

        conn.close()
        return bool(is_valid)

    def user_exists(self, username: str) -> bool:
        """Check if a user exists.

        Args:
            username: Username to check

        Returns:
            True if user exists, False otherwise
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
            return cursor.fetchone() is not None
        except sqlite3.Error as e:
            logger.error(f"Error checking user existence: {e}")
            return False
        finally:
            conn.close()

    def register_user(self, username: str, password: str, is_admin: bool = False) -> bool:
        """Register a new user.

        Args:
            username: Username for new user
            password: Password for new user
            is_admin: Whether user should have admin privileges

        Returns:
            True if registration successful, False if username exists
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Check if user exists
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        if cursor.fetchone() is not None:
            conn.close()
            return False

        # Hash password and insert user
        hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())

        try:
            cursor.execute(
                """
                INSERT INTO users (username, password_hash, is_admin)
                VALUES (?, ?, ?)
            """,
                (username, hashed, is_admin),
            )
            conn.commit()
            success = True
        except sqlite3.IntegrityError:
            success = False

        conn.close()
        return success

    def change_password(self, username: str, old_password: str, new_password: str) -> bool:
        """Change user password.

        Args:
            username: Username
            old_password: Current password
            new_password: New password

        Returns:
            True if password changed successfully
        """
        # First authenticate with old password
        if not self.authenticate(username, old_password):
            return False

        # Update password
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        hashed = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt())

        cursor.execute(
            """
            UPDATE users SET password_hash = ?
            WHERE username = ?
        """,
            (hashed, username),
        )

        conn.commit()
        conn.close()
        return True

    def get_user_info(self, username: str) -> Optional[Dict]:
        """Get user information.

        Args:
            username: Username to look up

        Returns:
            User info dict or None if not found
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, username, created_at, last_login, is_admin
            FROM users WHERE username = ?
        """,
            (username,),
        )

        result = cursor.fetchone()
        conn.close()

        if result is None:
            return None

        return {
            "id": result[0],
            "username": result[1],
            "created_at": result[2],
            "last_login": result[3],
            "is_admin": bool(result[4]),
        }

    def list_users(self) -> list:
        """List all users.

        Returns:
            List of user dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, username, created_at, last_login, is_admin
            FROM users ORDER BY username
        """
        )

        users = []
        for row in cursor.fetchall():
            users.append(
                {"id": row[0], "username": row[1], "created_at": row[2], "last_login": row[3], "is_admin": bool(row[4])}
            )

        conn.close()
        return users

    def delete_user(self, username: str) -> bool:
        """Delete a user.

        Args:
            username: Username to delete

        Returns:
            True if deletion successful
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM users WHERE username = ?", (username,))
        deleted = cursor.rowcount > 0

        conn.commit()
        conn.close()
        return deleted
