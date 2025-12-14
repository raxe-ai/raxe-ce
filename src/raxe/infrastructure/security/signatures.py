"""Cryptographic signature verification for packs.

Uses Ed25519 for fast, secure signatures.
"""
import base64
import hashlib
from pathlib import Path

try:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519

    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False


class SignatureError(Exception):
    """Signature verification failed."""

    pass


class SignatureVerifier:
    """
    Verify cryptographic signatures on rule packs.

    Uses Ed25519 for performance and security:
    - Fast verification (<1ms)
    - Small signatures (64 bytes)
    - Strong security (128-bit)
    """

    # Embedded RAXE public key (rotatable)
    # In production, this would be embedded during build
    RAXE_PUBLIC_KEY_PEM = """-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAGb9ECWmEzf6FQbrBZ9w7lshQhqowtrbLDFw4rXAxZuE=
-----END PUBLIC KEY-----"""

    def __init__(self, public_key_pem: str | None = None):
        """
        Initialize verifier.

        Args:
            public_key_pem: Optional custom public key (for testing)
        """
        if not CRYPTO_AVAILABLE:
            raise ImportError(
                "cryptography package required for signature verification. "
                "Install with: pip install cryptography"
            )

        pem = public_key_pem or self.RAXE_PUBLIC_KEY_PEM
        self.public_key = self._load_public_key(pem)

    def _load_public_key(self, pem: str) -> "ed25519.Ed25519PublicKey":
        """Load Ed25519 public key from PEM."""
        public_key = serialization.load_pem_public_key(pem.encode())

        if not isinstance(public_key, ed25519.Ed25519PublicKey):
            raise ValueError("Key must be Ed25519")

        return public_key

    def verify_pack(
        self, pack_dir: Path, signature: str, signature_algorithm: str
    ) -> bool:
        """
        Verify pack signature.

        Args:
            pack_dir: Directory containing pack files
            signature: Base64-encoded signature
            signature_algorithm: Algorithm (must be "ed25519")

        Returns:
            True if signature valid

        Raises:
            SignatureError: If verification fails
        """
        if signature_algorithm != "ed25519":
            raise SignatureError(
                f"Unsupported signature algorithm: {signature_algorithm}"
            )

        # Parse signature
        if not signature.startswith("ed25519:"):
            raise SignatureError("Signature must start with 'ed25519:'")

        sig_b64 = signature.split(":", 1)[1]

        try:
            signature_bytes = base64.b64decode(sig_b64)
        except Exception as e:
            raise SignatureError(f"Invalid base64 signature: {e}") from e

        # Hash pack contents
        pack_hash = self._hash_pack_contents(pack_dir)

        # Verify signature
        try:
            self.public_key.verify(signature_bytes, pack_hash)
            return True
        except InvalidSignature as e:
            raise SignatureError("Pack signature verification failed") from e

    def _hash_pack_contents(self, pack_dir: Path) -> bytes:
        """
        Create deterministic hash of pack contents.

        Hashes:
        1. pack.yaml manifest
        2. All rule YAML files (sorted by path)

        Returns:
            SHA-256 hash of pack contents
        """
        hasher = hashlib.sha256()

        # Hash manifest
        manifest_path = pack_dir / "pack.yaml"
        if manifest_path.exists():
            with open(manifest_path, "rb") as f:
                hasher.update(f.read())

        # Hash all rule files (sorted for determinism)
        rule_files = sorted(pack_dir.rglob("*.yaml"))
        rule_files = [f for f in rule_files if f.name != "pack.yaml"]

        for rule_file in rule_files:
            # Include relative path in hash
            rel_path = rule_file.relative_to(pack_dir)
            hasher.update(str(rel_path).encode())

            # Include file contents
            with open(rule_file, "rb") as f:
                hasher.update(f.read())

        return hasher.digest()

    def generate_signature(self, pack_dir: Path, private_key_pem: str) -> str:
        """
        Generate signature for pack (RAXE internal use only).

        Args:
            pack_dir: Pack directory
            private_key_pem: Ed25519 private key in PEM format

        Returns:
            Signature in format "ed25519:<base64>"
        """
        # Load private key
        private_key = serialization.load_pem_private_key(
            private_key_pem.encode(), password=None
        )

        if not isinstance(private_key, ed25519.Ed25519PrivateKey):
            raise ValueError("Key must be Ed25519")

        # Hash pack contents
        pack_hash = self._hash_pack_contents(pack_dir)

        # Sign
        signature_bytes = private_key.sign(pack_hash)

        # Encode
        sig_b64 = base64.b64encode(signature_bytes).decode()

        return f"ed25519:{sig_b64}"
