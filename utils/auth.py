import requests
import qrcode
import io
import base64
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import random
import execjs
import json

# 从 Flask 中导入 current_app，用于记录日志
from flask import current_app

BASE_URL = "https://music.163.com"
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Safari/605.1.15"
]

def get_headers():
    # 如果仅想在调试时查看 UA 切换，可以加个 debug 日志
    ua = random.choice(USER_AGENTS)
    current_app.logger.debug(f"使用的 User-Agent: {ua}")
    return {
        "Host": "music.163.com",
        "Referer": BASE_URL,
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": ua,
    }

def encrypted_request(data):
    """
    加密请求参数
    """
    current_app.logger.debug("开始加载本地加密 JS 文件 main.js")
    try:
        with open("static/main.js", "r", encoding="utf-8") as f:
            js_code = f.read()
    except FileNotFoundError:
        current_app.logger.error("main.js 文件未找到，请确保文件路径正确")
        raise

    ctx = execjs.compile(js_code)
    result = ctx.call("get_param", json.dumps(data, separators=(",", ":")))
    current_app.logger.debug("加密完成，返回加密后的 params 和 encSecKey")
    return {"params": result["encText"], "encSecKey": result["encSecKey"]}

def get_qrcode_unikey():
    """
    获取用于登录二维码的 unikey
    """
    current_app.logger.info("准备向服务端请求二维码 unikey")
    url = f"{BASE_URL}/weapi/login/qrcode/unikey"
    data = {"type": 1}

    try:
        resp = requests.post(url, data=encrypted_request(data), headers=get_headers())
        if resp.status_code == 200 and resp.json().get("code") == 200:
            unikey = resp.json()["unikey"]
            current_app.logger.info(f"成功获取 unikey: {unikey}")
            return unikey
        else:
            current_app.logger.error(
                f"获取 unikey 失败，状态码: {resp.status_code}, 响应: {resp.text}"
            )
            raise Exception("获取 unikey 失败")
    except Exception as e:
        current_app.logger.exception(f"获取 unikey 过程中出现异常: {str(e)}")
        raise

def generate_qrcode_image(unikey):
    """
    生成登录二维码并返回 base64
    """
    current_app.logger.info(f"开始生成二维码，unikey={unikey}")
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4
        )
        qr.add_data(f"{BASE_URL}/login?codekey={unikey}")
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        qr_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
        current_app.logger.debug("二维码已转换为 base64 编码")
        return qr_base64
    except Exception as e:
        current_app.logger.exception(f"生成二维码时出现异常: {str(e)}")
        raise

def get_user_profile(cookies):
    """
    通过已登录的 cookies 获取用户信息
    """
    current_app.logger.info("获取用户信息...")
    url = f"{BASE_URL}/weapi/w/nuser/account/get"

    try:
        resp = requests.post(url, data=encrypted_request({}), headers=get_headers(), cookies=cookies)
        if resp.status_code == 200:
            current_app.logger.debug(f"用户信息响应数据: {resp.json()}")
            return resp.json()
        else:
            current_app.logger.error(
                f"请求用户信息失败，状态码: {resp.status_code}, 响应: {resp.text}"
            )
            return {}
    except Exception as e:
        current_app.logger.exception(f"获取用户信息过程中出现异常: {str(e)}")
        return {}

def check_login_status_once(unikey):
    """
    检测二维码登录状态
    """
    current_app.logger.info("开始检测二维码登录状态")
    url = f"{BASE_URL}/weapi/login/qrcode/client/login"
    data = {"key": unikey, "type": 1, "csrf_token": ""}

    try:
        resp = requests.post(url, data=encrypted_request(data), headers=get_headers())
        result = resp.json()
        current_app.logger.debug(f"登录状态返回: {result}")

        if result.get("code") == 803:
            # 表示登录成功
            current_app.logger.info("二维码登录成功")
            cookies = resp.cookies.get_dict()
            result["cookies"] = cookies

            # 尝试获取用户信息
            profile = get_user_profile(cookies)
            result["profile"] = profile
        else:
            # 未登录成功或者其他情况
            current_app.logger.info(f"二维码登录状态码: {result.get('code')}")
        return result

    except Exception as e:
        current_app.logger.exception(f"检测二维码登录状态时出现异常: {str(e)}")
        raise

def get_retry_session():
    """
    返回一个带重试机制的 session
    """
    current_app.logger.debug("创建带重试机制的 Session 对象")
    session = requests.Session()
    retry = Retry(
        total=10,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET", "POST"]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session
