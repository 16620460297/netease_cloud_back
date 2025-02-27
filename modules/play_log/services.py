from flask import jsonify, request
from .models import PlayLog
from sqlalchemy import text
from utils.db import db
def set_play_log():
    try:
        data = request.json
        print(data)
        sql = text("""
            INSERT INTO play_logs 
            (user_id, song_id, song_name, current_position, song_duration, played_at)
            VALUES (:user_id, :song_id, :song_name, :current_time, :duration, NOW())
            ON DUPLICATE KEY UPDATE 
              current_position = VALUES(current_position),
              song_duration = VALUES(song_duration),
              played_at = NOW(),
              update_time = NOW()
        """)
        db.session.execute(sql, {
            'user_id': data['user_id'],
            'song_id': data['song_id'],
            'song_name': data.get('song_name', ''),
            'current_time': data['current_time'],
            'duration': data['duration']
        })
        db.session.commit()
        return jsonify({"code": 200, "msg": "播放记录已保存"})
    except Exception as e:
        return jsonify({"code": 500, "msg": str(e)})

def get_play_logs():
    from app import db  # 在函数内部导入 db
    try:
        user_id = request.args.get('user_id')
        if not user_id:
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
        return jsonify({"code": 200, "data": logs})
    except Exception as e:
        return jsonify({"code": 500, "msg": str(e)})
