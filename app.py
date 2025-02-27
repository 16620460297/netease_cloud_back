import logging
from flask import Flask
from flask_cors import CORS
from utils.db import db

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

        # ---- 日志部分开始 ----
        # 获取 Flask 自带的 logger
        flask_logger = app.logger

        # 创建自定义的 MySQL Handler
        mysql_handler = MySQLLogHandler()

        # 你也可以在这里配置一个基础 Formatter
        formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
        )
        mysql_handler.setFormatter(formatter)

        # 给 logger 加上这个 handler
        flask_logger.addHandler(mysql_handler)

        # 如果想把日志级别调低一点，一般 DEBUG 或 INFO
        flask_logger.setLevel(logging.DEBUG)
        # ---- 日志部分结束 ----

    return app

if __name__ == '__main__':
    app = create_app()
    app.run('0.0.0.0', debug=True, port=5000)
