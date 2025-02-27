from flask import jsonify, request, current_app
from .models import PlayLog
from sqlalchemy import text
from utils.db import db


def set_play_log():
    try:
        data = request.json

        # 记录收到的请求数据（DEBUG 级别）
        current_app.logger.debug(f"Received set_play_log request data: {data}")

        sql = text("""
            INSERT INTO play_logs 
            (user_id, song_id, song_name, current_position, song_duration, played_at)
            VALUES (:user_id, :song_id, :song_name, :current_time, :duration, NOW())
            ON DUPLICATE KEY UPDATE 
                current_position = VALUES(current_position),
                song_duration   = VALUES(song_duration),
                played_at       = NOW(),
                update_time     = NOW()
        """)
        db.session.execute(sql, {
            'user_id': data['user_id'],
            'song_id': data['song_id'],
            'song_name': data.get('song_name', ''),
            'current_time': data['current_time'],
            'duration': data['duration']
        })
        db.session.commit()

        # 成功插入/更新播放日志时（INFO 级别）
        current_app.logger.info(
            f"Successfully saved play log for user_id={data['user_id']}, song_id={data['song_id']}.")

        return jsonify({"code": 200, "msg": "播放记录已保存"})
    except Exception as e:
        # 出现异常时（ERROR 级别）
        current_app.logger.error(f"Error in set_play_log: {str(e)}")
        return jsonify({"code": 500, "msg": str(e)})


def get_play_logs():
    try:
        user_id = request.args.get('user_id')

        # 记录收到的请求参数（DEBUG 级别）
        current_app.logger.debug(f"Received get_play_logs request with user_id={user_id}")

        if not user_id:
            current_app.logger.warning("get_play_logs called without user_id parameter.")
            return jsonify({"code": 400, "msg": "缺少 user_id 参数"})

        sql = text("""
            SELECT 
                song_id,
                song_name,
                CASE 
                    WHEN current_position >= song_duration * 0.9 THEN 0
                    ELSE current_position
                END AS adjusted_current_time,
                song_duration,
                played_at
            FROM play_logs
            WHERE user_id = :user_id
            ORDER BY played_at DESC
            LIMIT 100
        """)

        result = db.session.execute(sql, {'user_id': user_id})
        logs = [dict(row._mapping) for row in result]

        # 成功查询时（INFO 级别）
        current_app.logger.info(f"Successfully retrieved {len(logs)} play logs for user_id={user_id}.")

        return jsonify({"code": 200, "data": logs})
    except Exception as e:
        current_app.logger.error(f"Error in get_play_logs: {str(e)}")
        return jsonify({"code": 500, "msg": str(e)})
