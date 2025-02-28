import time
from flask import jsonify, request, current_app
from sqlalchemy import text
from utils.db import db
from utils.redis_client import get_redis_client

LOG_BUFFER = []  # 存储日志的临时列表
LAST_FLUSH_TIME = 0
FLUSH_INTERVAL = 60  # 间隔多少秒汇总一次

def set_play_log():
    """
    将播放日志先存入Redis，减少频繁写数据库的压力。
    """
    global LAST_FLUSH_TIME

    try:
        data = request.json
        # 将“收到请求的数据”日志改为中文
        # current_app.logger.debug(f"【调试】收到 set_play_log 请求，数据: {data}")

        # 获取Redis连接
        redis_client = get_redis_client()

        user_id = data['user_id']
        song_id = data['song_id']
        song_name = data.get('song_name', '')
        current_time_ = data['current_time']
        duration = data['duration']

        # Redis的Key，可以根据业务做更灵活的设计
        key = f"play_log:{user_id}:{song_id}"

        # 使用 hset 命令存储多个字段
        redis_client.hset(key, "user_id", user_id)
        redis_client.hset(key, "song_id", song_id)
        redis_client.hset(key, "song_name", song_name)
        redis_client.hset(key, "current_time", current_time_)
        redis_client.hset(key, "duration", duration)
        redis_client.hset(key, "last_update", time.time())  # 设置最后更新时间

        # 设置Key的过期时间为1天（可选）
        redis_client.expire(key, 24 * 3600)

        # === 记录到内存 LOG_BUFFER，用于定期做批量汇总日志 ===
        LOG_BUFFER.append((user_id, song_id, song_name, current_time_, duration))

        now = time.time()
        # 如果超过指定时间（FLUSH_INTERVAL）才真正批量输出一次
        if now - LAST_FLUSH_TIME >= FLUSH_INTERVAL:
            # 将日志改为中文
            log_message = (
                f"【批量日志】在过去 {FLUSH_INTERVAL} 秒内，共有 {len(LOG_BUFFER)} 条播放日志被记录。"
                f"示例(前3条): {LOG_BUFFER[:3]}"
            )
            current_app.logger.info(log_message)

            # 清空列表，更新时间
            LOG_BUFFER.clear()
            LAST_FLUSH_TIME = now

        return jsonify({"code": 200, "msg": "播放记录已缓存至Redis"})

    except Exception as e:
        current_app.logger.error(f"【错误】在 set_play_log 中出现异常: {str(e)}")
        return jsonify({"code": 500, "msg": str(e)})


def get_play_logs():
    """
    从MySQL获取播放日志示例
    """
    try:
        user_id = request.args.get('user_id')

        # 将“收到请求”的日志改为中文
        current_app.logger.debug(f"【调试】收到 get_play_logs 请求，user_id={user_id}")

        if not user_id:
            current_app.logger.warning("【警告】get_play_logs 缺少 user_id 参数。")
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

        current_app.logger.info(f"【信息】成功查询到 user_id={user_id} 的播放日志，共 {len(logs)} 条。")

        return jsonify({"code": 200, "data": logs})
    except Exception as e:
        current_app.logger.error(f"【错误】在 get_play_logs 中出现异常: {str(e)}")
        return jsonify({"code": 500, "msg": str(e)})


def flush_redis_play_logs(threshold_seconds=30):
    """
    将Redis里的播放日志写回MySQL。
    threshold_seconds: 距离上次更新超过多少秒，才视为需要写回
    """
    try:
        # 可以改成中文
        print("【信息】开始执行 flush_redis_play_logs")
        redis_client = get_redis_client()

        pattern = "play_log:*"
        keys = redis_client.keys(pattern)
        now_ts = time.time()

        current_app.logger.debug(f"【调试】执行 flush_redis_play_logs，共找到 {len(keys)} 个匹配 {pattern} 的Key。")

        for key in keys:
            data = redis_client.hgetall(key)
            if not data:
                continue

            # 解码 Redis 返回的 bytes -> str (Python3)
            decoded = {k: v for k, v in data.items()}

            last_update_str = decoded.get("last_update", "0")
            try:
                last_update = float(last_update_str)
            except ValueError:
                last_update = 0

            # 判断是否超过写回阈值
            if (now_ts - last_update) >= threshold_seconds:
                try:
                    user_id = decoded["user_id"]
                    song_id = decoded["song_id"]
                    song_name = decoded.get("song_name", "")
                    current_time_ = decoded.get("current_time", "0")
                    duration = decoded.get("duration", "0")

                    # 中文日志
                    current_app.logger.debug(
                        f"【写回操作】即将写回 key={key} 到数据库: user_id={user_id}, song_id={song_id}, "
                        f"current_time={current_time_}, duration={duration}"
                    )

                    # 写回数据库
                    sql = text("""
                        INSERT INTO play_logs 
                            (user_id, song_id, song_name, current_position, song_duration, played_at, update_time)
                        VALUES 
                            (:user_id, :song_id, :song_name, :current_position, :song_duration, NOW(), NOW())
                        ON DUPLICATE KEY UPDATE 
                            song_name        = VALUES(song_name),
                            current_position = VALUES(current_position),
                            song_duration    = VALUES(song_duration),
                            played_at        = VALUES(played_at),
                            update_time      = VALUES(update_time)
                    """)
                    db.session.execute(sql, {
                        'user_id': user_id,
                        'song_id': song_id,
                        'song_name': song_name,
                        'current_position': current_time_,
                        'song_duration': duration
                    })
                    db.session.commit()

                    # 写库成功后，删除Redis中的key
                    redis_client.delete(key)
                    current_app.logger.info(f"【成功】key={key} 已写回数据库，并从Redis删除。")
                    print("【成功】写回并删除 Redis 中的 key=", key)
                except Exception as e:
                    # 写库失败，就记录日志
                    current_app.logger.error(f"【错误】写回MySQL失败，key={key}，异常信息={str(e)}")
                    # 若不删除 key，下次定时任务还会再尝试写回

        current_app.logger.info("【信息】flush_redis_play_logs 执行完毕！")
        return jsonify({"code": 200, "msg": "flush_redis_play_logs 执行完毕"})

    except Exception as e:
        current_app.logger.error(f"【错误】在 flush_redis_play_logs 中出现异常: {str(e)}")
        return jsonify({"code": 500, "msg": str(e)})
