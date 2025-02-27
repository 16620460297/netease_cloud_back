from flask import jsonify, request
from utils.auth import get_headers, get_retry_session
from .models import Playlist
import json
import requests
from utils.db import db


def show_playlist():
    uid = request.args.get('uid')
    if not uid:
        return jsonify({"code": 400, "msg": "缺少 uid 参数"})

    # 先查询数据库中是否已有此 UID 的歌单数据
    playlist = Playlist.query.filter_by(user_id=uid).first()

    # 准备调用外部接口
    url = f"http://music.163.com/api/user/playlist/?offset=0&limit=100&uid={uid}"

    try:
        resp = requests.get(url, headers=get_headers())
    except Exception as e:
        # 如果在请求阶段就抛出了异常
        if playlist:
            # 数据库有记录就返回
            return jsonify({
                "code": 200,
                "msg": "接口请求异常，使用数据库中的歌单数据",
                "data": json.loads(playlist.playlist_data)
            })
        else:
            # 数据库中无记录就无法继续
            return jsonify({"code": 500, "msg": f"获取歌单失败，且数据库中无数据；异常信息: {e}"})

    # 如果外部接口返回的状态码不是200，视为获取失败
    if resp.status_code != 200:
        if playlist:
            return jsonify({
                "code": 200,
                "msg": "接口获取失败，使用数据库中的歌单数据",
                "data": json.loads(playlist.playlist_data)
            })
        else:
            return jsonify({"code": 500, "msg": "获取歌单失败，且数据库中无数据"})

    # 走到这里，说明接口请求成功，并且 status_code == 200
    playlist_data = resp.json()

    if not playlist:
        # 数据库中不存在，直接插入
        new_playlist = Playlist(
            user_id=uid,
            playlist_data=json.dumps(playlist_data)
        )
        db.session.add(new_playlist)
        db.session.commit()
        return jsonify({"code": 200, "msg": "歌单数据已存储", "data": playlist_data})
    else:
        # 如果数据库里已经存在，先比较
        existing_data = json.loads(playlist.playlist_data)
        if existing_data == playlist_data:
            # 数据完全一致，无需更新
            return jsonify({
                "code": 200,
                "msg": "数据库中的歌单数据与接口相同，未做更新",
                "data": existing_data
            })
        else:
            # 数据不一致，更新数据库
            playlist.playlist_data = json.dumps(playlist_data)
            db.session.commit()
            return jsonify({
                "code": 200,
                "msg": "歌单数据已更新",
                "data": playlist_data
            })

def get_playlist_detail():
    playlist_id = request.args.get('id')
    if not playlist_id:
        return jsonify({"code": 400, "msg": "缺少歌单ID"})
    required_cookies = {
        'MUSIC_U': request.cookies.get('MUSIC_U'),
        '__csrf': request.cookies.get('__csrf')
    }
    if not all(required_cookies.values()):
        return jsonify({"code": 401, "msg": "认证失败，请确保已登录"})
    try:
        url = f"https://music.163.com/api/playlist/detail?id={playlist_id}"
        session = get_retry_session()
        resp = session.get(url, headers=get_headers(), cookies=required_cookies)
        if resp.status_code != 200:
            raise Exception(f"接口返回错误状态码: {resp.status_code}")
        data = resp.json()
        if 'result' not in data:
            raise Exception("返回数据缺少 'result' 字段")
        playlist = data['result']
        processed = {
            "playlist_id": playlist.get('id'),
            "name": playlist.get('name', '未知歌单'),
            "tracks": [
                {
                    "sort_id": idx + 1,
                    "picurl": t.get('album', {}).get('picUrl') or t.get('album', {}).get('blurPicUrl', ''),
                    "song_id": t.get('id'),
                    "title": t.get('name', '未知曲目'),
                    "duration": f"{t.get('duration', 0) // 1000 // 60:02d}:{t.get('duration', 0) // 1000 % 60:02d}",
                    "artists": ", ".join(a['name'] for a in t.get('artists', []) if a.get('name')),
                    "album": t.get('album', {}).get('name', '')
                }
                for idx, t in enumerate(playlist.get('tracks', []))
            ]
        }
        return jsonify({"code": 200, "data": processed})
    except Exception as e:
        return jsonify({"code": 500, "msg": "服务器处理异常", "error_detail": str(e)})


# 在 playlist_bp 或其它合适的蓝图里

def get_single_song_detail():
    song_id = request.args.get('song_id')
    if not song_id:
        return jsonify({"code": 400, "msg": "缺少 song_id"})

    # 构建网易云的单曲详情请求
    url = f"https://music.163.com/api/song/detail?ids=[{song_id}]"
    try:
        resp = requests.get(url)  # 这里可根据你项目需求，添加 headers/cookies 等
        if resp.status_code != 200:
            return jsonify({"code": 500, "msg": "获取单曲详情失败，状态码不为 200"})
        data = resp.json()
        # data 结构示例：{"songs":[{"id":..., "name":"...", ...}], "code":200}
        songs = data.get('songs', [])
        if not songs:
            return jsonify({"code": 404, "msg": "歌曲信息为空"})
        song_info = songs[0]
        return jsonify({"code": 200, "data": song_info})
    except Exception as e:
        return jsonify({"code": 500, "msg": "获取单曲详情出现异常", "error": str(e)})
