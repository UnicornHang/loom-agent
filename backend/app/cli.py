"""Operator commands. Example: python -m app.cli create-admin"""

import argparse
import getpass
import re

from sqlalchemy import select

from app.db import SessionLocal
from app.migrate import upgrade_database
from app.models import User
from app.security import hash_password


def create_admin(username: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,100}", username):
        raise SystemExit("用户名需为 3–100 位字母、数字、点、下划线或连字符")
    password = getpass.getpass("设置管理员密码（至少 12 位）：")
    if len(password) < 12 or len(password) > 128:
        raise SystemExit("密码长度必须为 12–128 位")
    if password != getpass.getpass("再次输入密码："):
        raise SystemExit("两次密码不一致")
    upgrade_database()
    with SessionLocal() as db:
        if db.scalar(select(User.id).where(User.tenant_id == "demo", User.username == username)):
            raise SystemExit("用户名已存在")
        db.add(User(tenant_id="demo", username=username, password_hash=hash_password(password), role="admin"))
        db.commit()
    print(f"管理员 {username} 已创建")


def main() -> None:
    parser = argparse.ArgumentParser(description="Loom 管理命令")
    parser.add_argument("command", choices=["create-admin", "migrate"])
    parser.add_argument("--username", default="admin")
    args = parser.parse_args()
    if args.command == "migrate":
        upgrade_database()
        print("数据库迁移完成")
    else:
        create_admin(args.username)


if __name__ == "__main__":
    main()
