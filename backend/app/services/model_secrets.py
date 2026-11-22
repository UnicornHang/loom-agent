import os
import tempfile
from pathlib import Path
from cryptography.fernet import Fernet


def cipher() -> Fernet:
    directory = Path(__file__).resolve().parents[2] / ".secrets"
    directory.mkdir(mode=0o700, exist_ok=True)
    path = directory / "model.key"
    if not path.exists():
        descriptor, temporary = tempfile.mkstemp(dir=directory)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(Fernet.generate_key())
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, path)
            except FileExistsError:
                pass
        finally:
            os.unlink(temporary)
    return Fernet(path.read_bytes())
