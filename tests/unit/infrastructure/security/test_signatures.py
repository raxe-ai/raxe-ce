"""Tests for signature verification."""

import pytest

from raxe.infrastructure.security.signatures import (
    CRYPTO_AVAILABLE,
    SignatureError,
    SignatureVerifier,
)

# Skip all tests if cryptography not available
pytestmark = pytest.mark.skipif(not CRYPTO_AVAILABLE, reason="cryptography package not installed")


class TestSignatureVerifier:
    """Test SignatureVerifier class."""

    def test_init_default_key(self):
        """Test verifier initialization with default key."""
        verifier = SignatureVerifier()
        assert verifier.public_key is not None

    def test_init_custom_key(self):
        """Test verifier initialization with custom key."""
        # Generate test key pair
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ed25519

        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = private_key.public_key()

        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()

        verifier = SignatureVerifier(public_key_pem=public_pem)
        assert verifier.public_key is not None

    def test_init_invalid_key_type(self):
        """Test verifier rejects non-Ed25519 keys."""
        # Valid RSA public key for testing
        invalid_pem = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAyLJmHqmKvp/VFW3rRdMj
ZCLwJhgL+mvN0PL8xFfPTw8fGLqPXNYp7n5rPpElPq8eQkYciFdjdN6MkqKdKPmJ
U2r7nGNlgq2Ln2J5mIlhJa0mcGZZhbRxFl9L7iF0cF1K8f9XMvYqF3mLKkqHJp6h
1NB6m5j3v6pP5YC7vH6jLMR5DcZLdGl3xQW7rLvKLkPyFJGcT8P8hK9N7F1jP5Nh
BPmJcqH1MlNPLzL6fRpLxPJ9F+vJbHMnP1cLqPNLfP8hLxKnPqFfGnLfJ6H8lLcF
LlNPqGfMnL8lKcJlLPF+GlKfJlLPGnLfJ6H8lLcFLlNPqGfMnL8lKcJlLPF+GlKf
JQIDAQAB
-----END PUBLIC KEY-----"""

        with pytest.raises(ValueError, match="Key must be Ed25519"):
            SignatureVerifier(public_key_pem=invalid_pem)

    def test_hash_pack_contents_deterministic(self, tmp_path):
        """Test deterministic pack hashing."""
        # Create test pack
        pack_dir = tmp_path / "test_pack"
        pack_dir.mkdir()

        (pack_dir / "pack.yaml").write_text("id: test\nversion: 1.0.0")

        rules_dir = pack_dir / "rules"
        rules_dir.mkdir()
        (rules_dir / "rule1.yaml").write_text("id: rule1\npattern: test")

        verifier = SignatureVerifier()
        hash1 = verifier._hash_pack_contents(pack_dir)
        hash2 = verifier._hash_pack_contents(pack_dir)

        # Hash should be deterministic
        assert hash1 == hash2

    def test_hash_pack_contents_includes_all_files(self, tmp_path):
        """Test pack hash includes all rule files."""
        pack_dir = tmp_path / "test_pack"
        pack_dir.mkdir()

        (pack_dir / "pack.yaml").write_text("id: test")

        rules_dir = pack_dir / "rules"
        rules_dir.mkdir()
        (rules_dir / "rule1.yaml").write_text("rule: 1")

        verifier = SignatureVerifier()
        hash1 = verifier._hash_pack_contents(pack_dir)

        # Add another file
        (rules_dir / "rule2.yaml").write_text("rule: 2")
        hash2 = verifier._hash_pack_contents(pack_dir)

        # Hash should change
        assert hash1 != hash2

    def test_hash_pack_contents_file_order_independent(self, tmp_path):
        """Test pack hash is independent of file creation order."""
        # Create pack 1
        pack1 = tmp_path / "pack1"
        pack1.mkdir()
        (pack1 / "pack.yaml").write_text("id: test")
        rules1 = pack1 / "rules"
        rules1.mkdir()
        (rules1 / "a.yaml").write_text("rule: a")
        (rules1 / "b.yaml").write_text("rule: b")

        # Create pack 2 (reverse order)
        pack2 = tmp_path / "pack2"
        pack2.mkdir()
        (pack2 / "pack.yaml").write_text("id: test")
        rules2 = pack2 / "rules"
        rules2.mkdir()
        (rules2 / "b.yaml").write_text("rule: b")
        (rules2 / "a.yaml").write_text("rule: a")

        verifier = SignatureVerifier()
        hash1 = verifier._hash_pack_contents(pack1)
        hash2 = verifier._hash_pack_contents(pack2)

        # Hashes should be identical (sorted)
        assert hash1 == hash2

    def test_verify_pack_invalid_algorithm(self, tmp_path):
        """Test pack verification rejects invalid algorithm."""
        pack_dir = tmp_path / "test_pack"
        pack_dir.mkdir()
        (pack_dir / "pack.yaml").write_text("id: test")

        verifier = SignatureVerifier()

        with pytest.raises(SignatureError, match="Unsupported signature algorithm"):
            verifier.verify_pack(pack_dir, "rsa:signature", "rsa")

    def test_verify_pack_invalid_format(self, tmp_path):
        """Test pack verification rejects invalid signature format."""
        pack_dir = tmp_path / "test_pack"
        pack_dir.mkdir()
        (pack_dir / "pack.yaml").write_text("id: test")

        verifier = SignatureVerifier()

        # Missing prefix
        with pytest.raises(SignatureError, match="must start with 'ed25519:'"):
            verifier.verify_pack(pack_dir, "invalid_signature", "ed25519")

    def test_verify_pack_invalid_base64(self, tmp_path):
        """Test pack verification rejects invalid base64."""
        pack_dir = tmp_path / "test_pack"
        pack_dir.mkdir()
        (pack_dir / "pack.yaml").write_text("id: test")

        verifier = SignatureVerifier()

        with pytest.raises(SignatureError, match="Invalid base64 signature"):
            verifier.verify_pack(pack_dir, "ed25519:not_valid_base64!!!", "ed25519")

    def test_verify_pack_wrong_signature(self, tmp_path):
        """Test pack verification rejects wrong signature."""
        pack_dir = tmp_path / "test_pack"
        pack_dir.mkdir()
        (pack_dir / "pack.yaml").write_text("id: test")

        verifier = SignatureVerifier()

        # Valid base64, but wrong signature
        import base64

        fake_signature = base64.b64encode(b"0" * 64).decode()

        with pytest.raises(SignatureError, match="verification failed"):
            verifier.verify_pack(pack_dir, f"ed25519:{fake_signature}", "ed25519")

    def test_generate_and_verify_signature(self, tmp_path):
        """Test signature generation and verification round-trip."""
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ed25519

        # Generate key pair
        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = private_key.public_key()

        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode()

        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()

        # Create test pack
        pack_dir = tmp_path / "test_pack"
        pack_dir.mkdir()
        (pack_dir / "pack.yaml").write_text("id: test\nversion: 1.0.0")

        rules_dir = pack_dir / "rules"
        rules_dir.mkdir()
        (rules_dir / "rule1.yaml").write_text("id: rule1\npattern: test")

        # Generate signature
        verifier = SignatureVerifier(public_key_pem=public_pem)
        signature = verifier.generate_signature(pack_dir, private_pem)

        # Verify signature
        assert signature.startswith("ed25519:")
        result = verifier.verify_pack(pack_dir, signature, "ed25519")
        assert result is True

    def test_verify_pack_tampered_content(self, tmp_path):
        """Test pack verification detects tampered content."""
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ed25519

        # Generate key pair
        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = private_key.public_key()

        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode()

        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()

        # Create test pack
        pack_dir = tmp_path / "test_pack"
        pack_dir.mkdir()
        (pack_dir / "pack.yaml").write_text("id: test\nversion: 1.0.0")

        rules_dir = pack_dir / "rules"
        rules_dir.mkdir()
        (rules_dir / "rule1.yaml").write_text("id: rule1\npattern: test")

        # Generate signature
        verifier = SignatureVerifier(public_key_pem=public_pem)
        signature = verifier.generate_signature(pack_dir, private_pem)

        # Tamper with content
        (rules_dir / "rule1.yaml").write_text("id: rule1\npattern: TAMPERED")

        # Verification should fail
        with pytest.raises(SignatureError, match="verification failed"):
            verifier.verify_pack(pack_dir, signature, "ed25519")

    def test_hash_pack_empty_directory(self, tmp_path):
        """Test hashing empty pack directory."""
        pack_dir = tmp_path / "empty_pack"
        pack_dir.mkdir()

        verifier = SignatureVerifier()
        hash_result = verifier._hash_pack_contents(pack_dir)

        # Should produce a hash even if empty
        assert hash_result is not None
        assert len(hash_result) == 32  # SHA-256 produces 32 bytes
