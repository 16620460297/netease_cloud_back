from flask import jsonify, request, current_app
from utils.auth import get_headers, get_retry_session
from .models import Playlist
import json
import requests
from utils.db import db

def show_playlist():
    # 进入函数就可以记录一个最简单的 INFO 级别日志
    current_app.logger.info("进入 show_playlist 函数")

    uid = request.args.get('uid')
    if not uid:
        # 缺少重要参数，可以记录成警告或者错误，根据业务严重程度决定
        current_app.logger.warning("请求中缺少 uid 参数")
        return jsonify({"code": 400, "msg": "缺少 uid 参数"})

    # 可以记录一下要查询的 UID
    current_app.logger.debug(f"准备查询 UID 为 {uid} 的歌单")

    # 先查询数据库中是否已有此 UID 的歌单数据
    playlist = Playlist.query.filter_by(user_id=uid).first()
    if playlist:
        current_app.logger.debug("数据库中已存在对应歌单记录")
    else:
        current_app.logger.debug("数据库中尚无此 UID 的歌单记录")

    # 准备调用外部接口
    url = f"http://music.163.com/api/user/playlist/?offset=0&limit=100&uid={uid}"

    try:
        resp = requests.get(url, headers=get_headers())
        current_app.logger.debug(f"已请求外部 API: {url}")
    except Exception as e:
        # 如果在请求阶段就抛出了异常
        current_app.logger.error(
            f"请求外部接口出现异常: {e}", exc_info=True
        )
        if playlist:
            current_app.logger.info("使用数据库中的歌单数据作为返回")
            return jsonify({
                "code": 200,
                "msg": "接口请求异常，使用数据库中的歌单数据",
                "data": json.loads(playlist.playlist_data)
            })
        else:
            current_app.logger.error("数据库中也无此 UID 的记录，无法提供数据")
            return jsonify({"code": 500, "msg": f"获取歌单失败，且数据库中无数据；异常信息: {e}"})

    # 如果外部接口返回的状态码不是200，视为获取失败
    if resp.status_code != 200:
        current_app.logger.warning(
            f"外部接口返回非 200 状态码: {resp.status_code}"
        )
        if playlist:
            current_app.logger.info("使用数据库中的歌单数据作为返回")
            return jsonify({
                "code": 200,
                "msg": "接口获取失败，使用数据库中的歌单数据",
                "data": json.loads(playlist.playlist_data)
            })
        else:
            current_app.logger.error("数据库中也无此 UID 的记录，无法提供数据")
            return jsonify({"code": 500, "msg": "获取歌单失败，且数据库中无数据"})

    # 走到这里，说明接口请求成功，并且 status_code == 200
    playlist_data = resp.json()
    current_app.logger.debug("外部接口返回数据成功")

    if not playlist:
        # 数据库中不存在，直接插入
        new_playlist = Playlist(
            user_id=uid,
            playlist_data=json.dumps(playlist_data)
        )
        db.session.add(new_playlist)
        db.session.commit()
        current_app.logger.info(f"数据库中无记录，为 UID={uid} 新增歌单数据")
        return jsonify({"code": 200, "msg": "歌单数据已存储", "data": playlist_data})
    else:
        # 如果数据库里已经存在，先比较
        existing_data = json.loads(playlist.playlist_data)
        if existing_data == playlist_data:
            # 数据完全一致，无需更新
            current_app.logger.info(f"数据库中 UID={uid} 的歌单与外部数据一致，无需更新")
            return jsonify({
                "code": 200,
                "msg": "数据库中的歌单数据与接口相同，未做更新",
                "data": existing_data
            })
        else:
            # 数据不一致，更新数据库
            playlist.playlist_data = json.dumps(playlist_data)
            db.session.commit()
            current_app.logger.info(f"数据库中 UID={uid} 的歌单已更新")
            return jsonify({
                "code": 200,
                "msg": "歌单数据已更新",
                "data": playlist_data
            })


def get_playlist_detail():
    current_app.logger.info("进入 get_playlist_detail 函数")

    playlist_id = request.args.get('id')
    if not playlist_id:
        current_app.logger.warning("缺少 playlist_id 参数")
        return jsonify({"code": 400, "msg": "缺少歌单ID"})

    # 检查认证
    required_cookies = {
        'MUSIC_U': request.cookies.get('MUSIC_U'),
        '__csrf': request.cookies.get('__csrf')
    }
    if not all(required_cookies.values()):
        current_app.logger.warning("用户缺少必要的认证 Cookie")
        return jsonify({"code": 401, "msg": "认证失败，请确保已登录"})

    try:
        url = f"https://music.163.com/api/playlist/detail?id={playlist_id}"
        session = get_retry_session()
        resp = session.get(url, headers=get_headers(), cookies=required_cookies)
        current_app.logger.debug(f"请求歌单详情 URL: {url}")

        if resp.status_code != 200:
            current_app.logger.warning(
                f"外部接口返回非 200 状态码: {resp.status_code}"
            )
            raise Exception(f"接口返回错误状态码: {resp.status_code}")

        data = resp.json()
        if 'result' not in data:
            current_app.logger.error("外部接口返回结果中缺少 'result' 字段")
            raise Exception("返回数据缺少 'result' 字段")

        playlist = data['result']
        processed = {
            "playlist_id": playlist.get('id'),
            "name": playlist.get('name', '未知歌单'),
            "tracks": [
                {
                    "sort_id": idx + 1,
                    "picurl": t.get('album', {}).get('picUrl')
                              or t.get('album', {}).get('blurPicUrl', ''),
                    "song_id": t.get('id'),
                    "title": t.get('name', '未知曲目'),
                    "duration": f"{t.get('duration', 0) // 1000 // 60:02d}:"
                                f"{t.get('duration', 0) // 1000 % 60:02d}",
                    "artists": ", ".join(
                        a['name'] for a in t.get('artists', []) if a.get('name')
                    ),
                    "album": t.get('album', {}).get('name', '')
                }
                for idx, t in enumerate(playlist.get('tracks', []))
            ]
        }

        current_app.logger.info(
            f"成功获取并处理歌单详情，playlist_id={playlist_id}"
        )
        return jsonify({"code": 200, "data": processed})

    except Exception as e:
        current_app.logger.error(
            f"获取歌单详情出现异常: {e}", exc_info=True
        )
        return jsonify({"code": 500, "msg": "服务器处理异常", "error_detail": str(e)})


def get_single_song_detail():
    current_app.logger.info("进入 get_single_song_detail 函数")

    song_id = request.args.get('song_id')
    if not song_id:
        current_app.logger.warning("缺少 song_id 参数")
        return jsonify({"code": 400, "msg": "缺少 song_id"})

    url = f"https://music.163.com/api/song/detail?ids=[{song_id}]"
    current_app.logger.debug(f"请求单曲详情 URL: {url}")

    try:
        resp = requests.get(url)  # 也可添加 headers, cookies 等
        if resp.status_code != 200:
            current_app.logger.warning(
                f"获取单曲详情失败，状态码: {resp.status_code}"
            )
            return jsonify({"code": 500, "msg": "获取单曲详情失败，状态码不为 200"})

        data = resp.json()
        songs = data.get('songs', [])
        if not songs:
            current_app.logger.warning("返回数据中未找到歌曲信息")
            return jsonify({"code": 404, "msg": "歌曲信息为空"})

        song_info = songs[0]
        current_app.logger.info(f"成功获取单曲详情 song_id={song_id}")
        return jsonify({"code": 200, "data": song_info})
    except Exception as e:
        current_app.logger.error(
            f"获取单曲详情出现异常: {e}", exc_info=True
        )
        return jsonify({"code": 500, "msg": "获取单曲详情出现异常", "error": str(e)})
