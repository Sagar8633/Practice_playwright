"""`python -m radar.web` - start the app on 127.0.0.1 and print where it is.

This exists so that the first thing a new install does is not "read the source to find the
factory function". It migrates the database, mints the session key if there is none, and says
the URL. If no account exists yet it says that too, because a login form that cannot succeed is
the worst possible first screen.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from radar.config import load_config
from radar.db import open_migrated
from radar.paths import DB_PATH
from radar.web.app import serve


def main() -> int:
    parser = argparse.ArgumentParser(prog="radar.web", description=__doc__)
    parser.add_argument("--db", type=Path, default=DB_PATH,
                        help="database file (default: %(default)s)")
    parser.add_argument("--host", default=None, help="override the configured bind address")
    parser.add_argument("--port", type=int, default=None, help="override the configured port")
    args = parser.parse_args()

    config = load_config(strict=False)
    if args.host or args.port:
        from dataclasses import replace

        web = replace(config.web, host=args.host or config.web.host,
                      port=args.port or config.web.port)
        config = replace(config, web=web)

    open_migrated(args.db).close()
    serve(config, args.db)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
