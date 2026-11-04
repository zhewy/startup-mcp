"""Local, read-only installed-app Drive OAuth credentials."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

SCOPE = "https://www.googleapis.com/auth/drive.readonly"
CLIENT = Path.home() / ".config" / "zmcp" / "oauth_client.json"
TOKEN = Path.home() / ".config" / "zmcp" / "token.json"


def _private_file(path: Path, content: str) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.exists() and path.is_symlink():
        raise ValueError("credential path must not be a symlink")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         delete=False) as stream:
            temporary = Path(stream.name)
            os.chmod(temporary, 0o600)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _dependencies():
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        raise ValueError("Install zmcp with the drive extra to enable OAuth") from None
    return Credentials, Request, InstalledAppFlow


def access_token(token_path: Path = TOKEN) -> str:
    Credentials, Request, _ = _dependencies()
    if not token_path.exists():
        raise ValueError("Drive authentication required: run zmcp-auth once locally")
    try:
        credentials = Credentials.from_authorized_user_file(str(token_path), [SCOPE])
        if not credentials.has_scopes([SCOPE]):
            raise ValueError("stored Drive credential lacks read-only scope")
        if not credentials.valid:
            if not credentials.refresh_token:
                raise ValueError("Drive consent expired: run zmcp-auth locally")
            credentials.refresh(Request())
            _private_file(token_path, credentials.to_json())
        return credentials.token
    except Exception:
        raise ValueError("Drive authentication failed: run zmcp-auth locally") from None


def main() -> None:
    """Run once in a local terminal, where browser consent is visible to the user."""
    _, _, InstalledAppFlow = _dependencies()
    client_path = Path(os.environ.get("ZMCP_OAUTH_CLIENT", CLIENT))
    token_path = Path(os.environ.get("ZMCP_OAUTH_TOKEN", TOKEN))
    if not client_path.is_file():
        raise SystemExit("Create a Google Desktop OAuth client and place its downloaded JSON at " + str(client_path))
    try:
        flow = InstalledAppFlow.from_client_secrets_file(str(client_path), scopes=[SCOPE])
        credentials = flow.run_local_server(port=0, open_browser=True)
        if not credentials.refresh_token:
            raise ValueError("Google did not grant offline renewal; retry consent")
        _private_file(token_path, credentials.to_json())
    except Exception:
        raise SystemExit("Drive consent failed; no credential was saved") from None
    print("Read-only Drive authentication saved locally.")


if __name__ == "__main__":
    main()
