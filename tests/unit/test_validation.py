"""Tests for validation utilities."""

from m8tes.utils.validation import validate_email, validate_password


class TestEmailValidation:
    """Test email validation function."""

    def test_valid_emails(self):
        """Test that valid emails pass validation."""
        valid_emails = [
            "user@example.com",
            "test.email@domain.co.uk",
            "name+tag@company.org",
            "user123@test-domain.com",
            "a@b.co",
        ]

        for email in valid_emails:
            assert validate_email(email) is None, f"Email {email} should be valid"

    def test_invalid_emails(self):
        """Test that invalid emails fail validation."""
        invalid_emails = [
            "",  # Empty
            "not-an-email",  # No @
            "@domain.com",  # No user part
            "user@",  # No domain
            "user@domain",  # No TLD
            "user space@domain.com",  # Space in user part
            "user@do main.com",  # Space in domain
            ".user@domain.com",  # Starts with dot
            "user.@domain.com",  # Ends with dot
        ]

        for email in invalid_emails:
            result = validate_email(email)
            assert result is not None, f"Email {email} should be invalid"
            assert isinstance(result, str), "Error should be a string"

    def test_empty_email(self):
        """Test that empty email returns appropriate error."""
        result = validate_email("")
        assert result == "Email is required"


class TestPasswordValidation:
    """Test password validation function."""

    def test_valid_passwords(self):
        """Test that valid passwords pass validation."""
        valid_passwords = [
            "password123",  # 8+ characters
            "longpassword",  # Long password
            "P@ssw0rd!",  # Complex password
            "pass with space",  # Contains whitespace but not whitespace-only
        ]

        for password in valid_passwords:
            assert validate_password(password) is None, f"Password '{password}' should be valid"

    def test_invalid_passwords(self):
        """Test that invalid passwords fail validation."""
        invalid_passwords = [
            "",  # Empty
            "short",  # Too short (5 chars)
            "1234567",  # Too short (7 chars)
        ]

        for password in invalid_passwords:
            result = validate_password(password)
            assert result is not None, f"Password '{password}' should be invalid"
            assert isinstance(result, str), "Error should be a string"

    def test_empty_password(self):
        """Test that empty password returns appropriate error."""
        result = validate_password("")
        assert result == "Password is required"

    def test_whitespace_only_password(self):
        """Test that whitespace-only passwords fail validation."""
        result = validate_password("        ")
        assert result == "Password cannot be only whitespace"

    def test_short_password(self):
        """Test that short password returns appropriate error."""
        result = validate_password("1234567")
        assert result == "Password must be at least 8 characters"

    def test_minimum_length_password(self):
        """Test that exactly 8 character password is valid."""
        result = validate_password("12345678")
        assert result is None
