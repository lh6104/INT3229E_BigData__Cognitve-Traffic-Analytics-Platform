"""Initialize shared secret once without exposing it in environment or command output."""
import os
import secrets
from pathlib import Path


def main():
    directory = Path(os.getenv('ONCALL_STATE_DIR', '/state'))
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / 'token'
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        return
    with os.fdopen(fd, 'w') as target:
        target.write(secrets.token_hex(32))
    uid = int(os.getenv('ONCALL_HOST_UID', '1000'))
    gid = int(os.getenv('ONCALL_HOST_GID', '1000'))
    if os.getuid() == 0:
        os.chown(path, uid, gid)
        os.chown(directory, uid, gid)


if __name__ == '__main__':
    main()
