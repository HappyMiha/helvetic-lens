"""Offline platform-administrator management for the single-server deployment."""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import func, select

from .auth import normalize_email, token_hash
from .config import DomainError, Settings
from .models import SecurityEvent, User
from .service import HelveticLens


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(prog="helvetic-lens-admin")
    commands = value.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="List current platform administrators")
    for command in ("promote", "demote"):
        child = commands.add_parser(command, help=f"{command.title()} an existing local account")
        child.add_argument("email")
    return value


def run(arguments: list[str] | None = None, *, settings: Settings | None = None) -> int:
    args = parser().parse_args(arguments)
    service = HelveticLens(settings or Settings())
    service.initialize()
    try:
        with service.db.session(include_all_organizations=True) as session:
            if args.command == "list":
                admins = list(
                    session.scalars(select(User).where(User.platform_admin.is_(True)).order_by(User.email))
                )
                if not admins:
                    print("No platform administrators configured.")
                for user in admins:
                    print(f"{user.email}\t{user.name}\t{user.id}")
                return 0

            email = normalize_email(args.email)
            user = session.scalar(select(User).where(User.email == email))
            if not user:
                raise DomainError(
                    "Create the local account before assigning platform access.", 404, "user_not_found"
                )
            desired = args.command == "promote"
            if user.platform_admin == desired:
                print(f"{email} is already {'a platform administrator' if desired else 'a regular user'}.")
                return 0
            if not desired:
                count = session.scalar(
                    select(func.count()).select_from(User).where(User.platform_admin.is_(True))
                )
                if count <= 1:
                    raise DomainError(
                        "Promote another platform administrator before removing the last one.",
                        409,
                        "last_platform_admin",
                    )
            user.platform_admin = desired
            session.add(
                SecurityEvent(
                    user_id=user.id,
                    kind="platform_admin_promoted" if desired else "platform_admin_demoted",
                    subject_hash=token_hash(email),
                )
            )
            session.commit()
            print(f"{email} {'promoted' if desired else 'demoted'}.")
            return 0
    except DomainError as error:
        print(error.message, file=sys.stderr)
        return 1
    finally:
        service.db.engine.dispose()


def main():
    raise SystemExit(run())


if __name__ == "__main__":
    main()
