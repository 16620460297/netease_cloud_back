import logging
from sqlalchemy import text
from utils.db import db  # 你的 SQLAlchemy 实例

class MySQLLogHandler(logging.Handler):
    def __init__(self, level=logging.NOTSET):
        super().__init__(level)

    def emit(self, record):
        try:
            # 格式化日志信息
            log_message = self.format(record)
            level = record.levelname
            pathname = record.pathname
            funcname = record.funcName
            lineno = record.lineno

            # 使用 SQLAlchemy 的方式插入
            sql = text("""
                INSERT INTO app_logs(level, message, pathname, funcname, lineno)
                VALUES (:level, :message, :pathname, :funcname, :lineno)
            """)
            params = {
                "level": level,
                "message": log_message,
                "pathname": pathname,
                "funcname": funcname,
                "lineno": lineno
            }

            db.session.execute(sql, params)
            db.session.commit()

        except Exception:
            self.handleError(record)
