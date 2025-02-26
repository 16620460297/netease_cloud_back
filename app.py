import json
import random
import time
import execjs
import requests
import qrcode
import io
import base64
from flask import Flask, jsonify, request
from flask_cors import CORS  # 导入 flask-cors

# 基础配置
BASE_URL = "https://music.163.com"
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Safari/605.1.15"
]

def get_headers():
    return {
        "Host": "music.163.com",
        "Referer": BASE_URL,
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": random.choice(USER_AGENTS),
    }

def encrypted_request(data):
    """执行参数加密"""
    with open("main.js", "r", encoding="utf-8") as f:
        js_code = f.read()
    ctx = execjs.compile(js_code)
    result = ctx.call("get_param", json.dumps(data, separators=(",", ":")))
    return {
        "params": result["encText"],
        "encSecKey": result["encSecKey"]
    }

def get_qrcode_unikey():
    """获取登录二维码的 unikey"""
    url = f"{BASE_URL}/weapi/login/qrcode/unikey"
    data = {"type": 1}
    response = requests.post(url, data=encrypted_request(data), headers=get_headers())
    if response.status_code == 200:
        result = response.json()
        if result["code"] == 200:
            return result["unikey"]
    raise Exception("获取 unikey 失败")

def generate_qrcode_image(unikey):
    """生成二维码图片并返回 base64 编码字符串"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    # 二维码中携带登录链接
    qr.add_data(f"{BASE_URL}/login?codekey={unikey}")
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
    return img_str

def check_login_status_once(unikey):
    """单次查询登录状态"""
    url = f"{BASE_URL}/weapi/login/qrcode/client/login"
    data = {
        "key": unikey,
        "type": 1,
        "csrf_token": ""
    }
    response = requests.post(url, data=encrypted_request(data), headers=get_headers())
    result = response.json()
    # 登录成功时处理cookie
    if result.get("code") == 803:  # 803表示登录成功
        cookies = response.cookies.get_dict()
        print("[登录成功] Cookies:", cookies)  # 打印cookie
        result["cookies"] = cookies  # 将cookie加入返回结果
    # 在返回结果前调用
    if result.get("code") == 803:
        profile = get_user_profile(cookies)
        print("[用户信息]", profile)
        result["profile"] = profile
    return result

app = Flask(__name__)
CORS(app)  # 跨域全开，允许所有来源的请求

@app.route('/api/qrcode', methods=['GET'])
def api_qrcode():
    """
    1. 获取 unikey
    2. 生成二维码图片（返回 base64 字符串）
    """
    try:
        unikey = get_qrcode_unikey()
        qr_code_base64 = generate_qrcode_image(unikey)
        return jsonify({
            "code": 200,
            "data": {
                "unikey": unikey,
                "qrCodeBase64": qr_code_base64
            }
        })
    except Exception as e:
        return jsonify({"code": 500, "msg": str(e)})

@app.route('/api/check_login', methods=['GET'])
def api_check_login():
    """
    前端传入 unikey，后端调用网易云接口检查二维码登录状态
    """
    unikey = request.args.get('unikey')
    if not unikey:
        return jsonify({"code": 400, "msg": "缺少 unikey 参数"})
    result = check_login_status_once(unikey)
    print(result)
    return jsonify(result)

# 此处可增加其他接口，例如用户歌单等

# 在登录成功后可添加用户信息获取逻辑
def get_user_profile(cookies):
    url = f"{BASE_URL}/weapi/w/nuser/account/get"
    response = requests.post(url,
        data=encrypted_request({}),
        headers=get_headers(),
        cookies=cookies
    )
    return response.json()



if __name__ == '__main__':
    app.run(debug=True, port=5000)
