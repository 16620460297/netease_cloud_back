
import time
from flask import jsonify, request, current_app
from sqlalchemy import text
from utils.db import db
from utils.redis_client import get_redis_client

def set_play_log():
    """
    将播放日志先存入Redis，减少频繁写数据库的压力。
    """
    try:
        data = request.json
        current_app.logger.debug(f"Received set_play_log request data: {data}")

        # 获取Redis连接
        redis_client = get_redis_client()

        user_id = data['user_id']
        song_id = data['song_id']
        song_name = data.get('song_name', '')
        current_time_ = data['current_time']
        duration = data['duration']

        # Redis的Key，可以根据业务做更灵活的设计
        key = f"play_log:{user_id}:{song_id}"

        # 使用hset命令存储多个字段
        redis_client.hset(key, "user_id", user_id)
        redis_client.hset(key, "song_id", song_id)
        redis_client.hset(key, "song_name", song_name)
        redis_client.hset(key, "current_time", current_time_)
        redis_client.hset(key, "duration", duration)
        redis_client.hset(key, "last_update", time.time())  # 设置最后更新时间

        # 可选：给这个Key设置个过期时间（例如1天）
        redis_client.expire(key, 24 * 3600)  # 1天

        current_app.logger.info(
            f"Successfully saved play log into Redis for user_id={user_id}, song_id={song_id}."
        )
        return jsonify({"code": 200, "msg": "播放记录已缓存至Redis"})

    except Exception as e:
        current_app.logger.error(f"Error in set_play_log: {str(e)}")
        return jsonify({"code": 500, "msg": str(e)})


def get_play_logs():
    """
    从MySQL获取播放日志示例
    """
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


def flush_redis_play_logs(threshold_seconds=30):
    """
    将Redis里的播放日志写回MySQL。
    threshold_seconds: 距离上次更新超过多少秒视为需要写回
    """
    try:
        print("开始执行 flush_redis_play_logs")
        redis_client = get_redis_client()

        pattern = "play_log:*"
        keys = redis_client.keys(pattern)
        now_ts = time.time()

        current_app.logger.debug(f"Starting flush_redis_play_logs. Found {len(keys)} keys matching '{pattern}'.")

        for key in keys:
            data = redis_client.hgetall(key)
            if not data:
                continue

            # 解码 Redis 返回的 bytes -> str (Python3)
            # data 是一个 dict, 需要对内部的 key/value 都进行 decode
            decoded = {k: v for k, v in data.items()}

            last_update_str = decoded.get("last_update", "0")
            try:
                last_update = float(last_update_str)
            except ValueError:
                last_update = 0

            # 判断是否超过阈值
            if (now_ts - last_update) >= threshold_seconds:
                try:
                    user_id = decoded["user_id"]
                    song_id = decoded["song_id"]
                    song_name = decoded.get("song_name", "")
                    current_time_ = decoded.get("current_time", "0")
                    duration = decoded.get("duration", "0")

                    current_app.logger.debug(
                        f"Flushing key={key} to DB. user_id={user_id}, song_id={song_id}, current_time={current_time_}, duration={duration}"
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
                    current_app.logger.info(f"Key={key} flushed to DB and removed from Redis.")
                    print("成功")
                except Exception as e:
                    # 写库失败，就记录日志，可根据需求决定是否删除Redis key
                    current_app.logger.error(f"写回MySQL失败, key={key}, err={str(e)}")
                    # 如果不删除key，那么下次定时任务还会再尝试写回
                    # 也可以根据需求配置“重试次数”或“转移到另一种错误队列”等

        current_app.logger.info("flush_redis_play_logs 执行完毕！")
        return jsonify({"code": 200, "msg": "flush_redis_play_logs 执行完毕"})

    except Exception as e:
        current_app.logger.error(f"Error in flush_redis_play_logs: {str(e)}")
        return jsonify({"code": 500, "msg": str(e)})



# import time
# from flask import jsonify, request, current_app
# from sqlalchemy import text
# from utils.db import db
# from utils.redis_client import get_redis_client
#
# def set_play_log():
#     """
#     将播放日志先存入Redis，减少频繁写数据库的压力。
#     """
#     try:
#         data = request.json
#         current_app.logger.debug(f"Received set_play_log request data: {data}")
#
#         # 获取Redis连接
#         redis_client = get_redis_client()
#
#         user_id = data['user_id']
#         song_id = data['song_id']
#         song_name = data.get('song_name', '')
#         current_time_ = data['current_time']
#         duration = data['duration']
#
#         # Redis的Key，可以根据业务做更灵活的设计
#         key = f"play_log:{user_id}:{song_id}"
#
#         # 使用hset命令存储多个字段
#         redis_client.hset(key, "user_id", user_id)
#         redis_client.hset(key, "song_id", song_id)
#         redis_client.hset(key, "song_name", song_name)
#         redis_client.hset(key, "current_time", current_time_)
#         redis_client.hset(key, "duration", duration)
#         redis_client.hset(key, "last_update", time.time())  # 设置最后更新时间
#
#         # 可选：给这个Key设置个过期时间（例如1天）
#         redis_client.expire(key, 24 * 3600)  # 1天
#
#         current_app.logger.info(
#             f"Successfully saved play log into Redis for user_id={user_id}, song_id={song_id}."
#         )
#         return jsonify({"code": 200, "msg": "播放记录已缓存至Redis"})
#
#     except Exception as e:
#         current_app.logger.error(f"Error in set_play_log: {str(e)}")
#         return jsonify({"code": 500, "msg": str(e)})
#
#
# def get_play_logs():
#     try:
#         user_id = request.args.get('user_id')
#
#         # 记录收到的请求参数（DEBUG 级别）
#         current_app.logger.debug(f"Received get_play_logs request with user_id={user_id}")
#
#         if not user_id:
#             current_app.logger.warning("get_play_logs called without user_id parameter.")
#             return jsonify({"code": 400, "msg": "缺少 user_id 参数"})
#
#         sql = text("""
#             SELECT
#                 song_id,
#                 song_name,
#                 CASE
#                     WHEN current_position >= song_duration * 0.9 THEN 0
#                     ELSE current_position
#                 END AS adjusted_current_time,
#                 song_duration,
#                 played_at
#             FROM play_logs
#             WHERE user_id = :user_id
#             ORDER BY played_at DESC
#             LIMIT 100
#         """)
#
#         result = db.session.execute(sql, {'user_id': user_id})
#         logs = [dict(row._mapping) for row in result]
#
#         # 成功查询时（INFO 级别）
#         current_app.logger.info(f"Successfully retrieved {len(logs)} play logs for user_id={user_id}.")
#
#         return jsonify({"code": 200, "data": logs})
#     except Exception as e:
#         current_app.logger.error(f"Error in get_play_logs: {str(e)}")
#         return jsonify({"code": 500, "msg": str(e)})
#
# def flush_redis_play_logs(threshold_seconds=300):
#     """
#     将Redis里的播放日志写回MySQL。
#     threshold_seconds: 距离上次更新超过多少秒视为需要写回
#     """
#     redis_client = get_redis_client()
#
#     pattern = "play_log:*"
#     keys = redis_client.keys(pattern)
#     now_ts = time.time()
#
#     for key in keys:
#         data = redis_client.hgetall(key)
#         if not data:
#             continue
#
#         last_update = float(data.get("last_update", 0))
#         # 如果离上次更新超过了 threshold_seconds，就写回数据库
#         if (now_ts - last_update) >= threshold_seconds:
#             try:
#                 user_id = data["user_id"]
#                 song_id = data["song_id"]
#                 song_name = data["song_name"]
#                 current_time_ = data["current_time"]
#                 duration = data["duration"]
#
#                 # 写回数据库
#                 sql = text("""
#                     INSERT INTO play_logs
#                     (user_id, song_id, song_name, current_position, song_duration, played_at)
#                     VALUES (:user_id, :song_id, :song_name, :current_time, :duration, NOW())
#                     ON DUPLICATE KEY UPDATE
#                         current_position = VALUES(current_position),
#                         song_duration   = VALUES(song_duration),
#                         played_at       = NOW(),
#                         update_time     = NOW()
#                 """)
#                 db.session.execute(sql, {
#                     'user_id': user_id,
#                     'song_id': song_id,
#                     'song_name': song_name,
#                     'current_time': current_time_,
#                     'duration': duration
#                 })
#                 db.session.commit()
#
#                 # 写库成功后，删除Redis中的key
#                 redis_client.delete(key)
#
#             except Exception as e:
#                 current_app.logger.error(f"写回MySQL失败, key={key}, err={str(e)}")
#                 # 如果你不删除key，那么下次定时任务还会再尝试写回
#                 # 看你希望的容错策略决定是否要删除
#
#     current_app.logger.info("flush_redis_play_logs 执行完毕！")



































#
# def get_play_logs():
#     try:
#         user_id = request.args.get('user_id')
#
#         # 记录收到的请求参数（DEBUG 级别）
#         current_app.logger.debug(f"Received get_play_logs request with user_id={user_id}")
#
#         if not user_id:
#             current_app.logger.warning("get_play_logs called without user_id parameter.")
#             return jsonify({"code": 400, "msg": "缺少 user_id 参数"})
#
#         sql = text("""
#             SELECT
#                 song_id,
#                 song_name,
#                 CASE
#                     WHEN current_position >= song_duration * 0.9 THEN 0
#                     ELSE current_position
#                 END AS adjusted_current_time,
#                 song_duration,
#                 played_at
#             FROM play_logs
#             WHERE user_id = :user_id
#             ORDER BY played_at DESC
#             LIMIT 100
#         """)
#
#         result = db.session.execute(sql, {'user_id': user_id})
#         logs = [dict(row._mapping) for row in result]
#
#         # 成功查询时（INFO 级别）
#         current_app.logger.info(f"Successfully retrieved {len(logs)} play logs for user_id={user_id}.")
#
#         return jsonify({"code": 200, "data": logs})
#     except Exception as e:
#         current_app.logger.error(f"Error in get_play_logs: {str(e)}")
#         return jsonify({"code": 500, "msg": str(e)})


# def get_play_logs():
#     """
#     读取播放日志，优先从Redis拿最新的记录。
#     也可以再去数据库拿历史数据，然后做合并。
#     """
#     try:
#         user_id = request.args.get('user_id')
#         current_app.logger.debug(f"Received get_play_logs request with user_id={user_id}")
#
#         if not user_id:
#             current_app.logger.warning("get_play_logs called without user_id parameter.")
#             return jsonify({"code": 400, "msg": "缺少 user_id 参数"})
#
#         redis_client = get_redis_client()
#         # 找到Redis中所有该用户的记录
#         pattern = f"play_log:{user_id}:*"
#         keys = redis_client.keys(pattern)
#
#         logs_in_redis = []
#         for key in keys:
#             data = redis_client.hgetall(key)
#             # hgetall 返回的是字符串，需要转int的自行转
#             if data:
#                 # 根据实际需求做类型转换
#                 record = {
#                     "song_id": int(data["song_id"]),
#                     "song_name": data["song_name"],
#                     "current_time": float(data["current_time"]),
#                     "duration": float(data["duration"]),
#                     # last_update 一般不返回给前端，仅内部用
#                 }
#                 logs_in_redis.append(record)
#
#         # 如果需要拿到以前写回数据库的老记录，可以再查一下数据库
#         # 此处做一个示例，拿到数据库中最近100条
#         sql = text("""
#             SELECT
#                 song_id,
#                 song_name,
#                 CASE
#                     WHEN current_position >= song_duration * 0.9 THEN 0
#                     ELSE current_position
#                 END AS adjusted_current_time,
#                 song_duration,
#                 played_at
#             FROM play_logs
#             WHERE user_id = :user_id
#             ORDER BY played_at DESC
#             LIMIT 100
#         """)
#         result = db.session.execute(sql, {'user_id': user_id})
#         logs_in_db = [dict(row._mapping) for row in result]
#
#         # 合并两个列表（如果同一个song_id既在Redis也在DB，可以自行去重或覆盖逻辑）
#         # 这里简单拼在一起做演示
#         combined_logs = logs_in_redis + logs_in_db
#
#         current_app.logger.info(
#             f"Successfully retrieved {len(combined_logs)} play logs (Redis + DB) for user_id={user_id}."
#         )
#         return jsonify({"code": 200, "data": combined_logs})
#
#     except Exception as e:
#         current_app.logger.error(f"Error in get_play_logs: {str(e)}")
#         return jsonify({"code": 500, "msg": str(e)})