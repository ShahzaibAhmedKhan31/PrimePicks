from __future__ import annotations

import logging
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_data_dir

logger = logging.getLogger(__name__)
SERVICE_NAME = "PrimePickGoodsListingGenerator"
SECRET_ACCOUNT = "openai_api_key"


class SecretStore:
    """Use the OS credential vault where possible, with encrypted local fallback.

    On Windows, keyring uses the current user's Credential Manager. The fallback
    exists for developer environments without an OS keyring and stores its key
    with the user's application data rather than in the repository.
    """

    def __init__(self) -> None:
        self.data_dir = get_data_dir()
        self._keyring = None
        try:
            import keyring

            backend = keyring.get_keyring()
            if getattr(backend, "priority", 0) > 0:
                self._keyring = keyring
        except Exception as error:  # a missing desktop keyring is not fatal
            logger.info("Credential vault unavailable; using encrypted local fallback (%s)", type(error).__name__)

    def get(self) -> str | None:
        if self._keyring is not None:
            try:
                value = self._keyring.get_password(SERVICE_NAME, SECRET_ACCOUNT)
                if value:
                    return value
            except Exception as error:
                logger.warning("Could not read OS credential vault (%s)", type(error).__name__)
        token_path = self.data_dir / "openai-key.bin"
        if not token_path.exists():
            return None
        try:
            return self._cipher().decrypt(token_path.read_bytes()).decode("utf-8")
        except (InvalidToken, OSError, UnicodeDecodeError) as error:
            logger.warning("Could not read encrypted API key (%s)", type(error).__name__)
            return None

    def set(self, value: str) -> None:
        if self._keyring is not None:
            try:
                self._keyring.set_password(SERVICE_NAME, SECRET_ACCOUNT, value)
                (self.data_dir / "openai-key.bin").unlink(missing_ok=True)
                return
            except Exception as error:
                logger.warning("Could not write OS credential vault; using encrypted fallback (%s)", type(error).__name__)
        token_path = self.data_dir / "openai-key.bin"
        token_path.write_bytes(self._cipher().encrypt(value.encode("utf-8")))
        self._restrict_permissions(token_path)

    def clear(self) -> None:
        if self._keyring is not None:
            try:
                self._keyring.delete_password(SERVICE_NAME, SECRET_ACCOUNT)
            except Exception:
                pass
        (self.data_dir / "openai-key.bin").unlink(missing_ok=True)

    def _cipher(self) -> Fernet:
        key_path = self.data_dir / "local-secret.key"
        if not key_path.exists():
            key_path.write_bytes(Fernet.generate_key())
            self._restrict_permissions(key_path)
        return Fernet(key_path.read_bytes())

    @staticmethod
    def _restrict_permissions(path: Path) -> None:
        try:
            path.chmod(0o600)
        except OSError:
            pass


secrets = SecretStore()
