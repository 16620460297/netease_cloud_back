import logging
from sched import scheduler

from flask import Flask
from flask_cors import CORS

from modules.play_log.services import flush_redis_play_logs
from utils.db import db
from flask_apscheduler import APScheduler
# 引入你自定义的 Handler
from utils.my_sql_handler   import MySQLLogHandler
def create_app():
    app = Flask(__name__)
    CORS(app)

    app.config.from_pyfile('config.py')

    db.init_app(app)

    with app.app_context():
        # 注册蓝图
        from modules.user.views import user_bp
        from modules.playlist.views import playlist_bp
        from modules.play_log.views import play_log_bp

        app.register_blueprint(user_bp)
        app.register_blueprint(playlist_bp)
        app.register_blueprint(play_log_bp)

        # 日志部分配置
        flask_logger = app.logger
        mysql_handler = MySQLLogHandler()
        formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
        )
        mysql_handler.setFormatter(formatter)
        flask_logger.addHandler(mysql_handler)
        flask_logger.setLevel(logging.DEBUG)

        # 定时任务部分
        scheduler = APScheduler()
        scheduler.init_app(app)
        scheduler.start()

        # 定义并添加定时任务
        def flush_redis_play_logs_job():
            with app.app_context():
                flush_redis_play_logs()

        scheduler.add_job(
            id='flush_redis_play_logs_task',
            func=flush_redis_play_logs_job,
            trigger='interval',
            seconds=60
        )

    return app

# 移除原来的装饰器定义
def cron_flush_redis_play_logs():
    flush_redis_play_logs()

if __name__ == '__main__':
    # 播放器~启动~
    app = create_app()
    app.run('0.0.0.0', debug=True, port=5000)
