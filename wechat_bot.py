# -*- coding: utf-8 -*-
"""
灰泽满微信公众号测试号机器人
- 接收文字/语音消息 → DeepSeek 生成回复 → 随机返回文字或语音
- GPT-SoVITS 语音合成
- 灰泽满人格（SOUL/SKILL/CORPUS）
- 支持消息去重 + 异步语音回复（客服消息接口）
"""
import os
import re
import sys
import time
import random
import hashlib
import subprocess
import threading
import xml.etree.ElementTree as ET
from pathlib import Path

import requests
from flask import Flask, request, make_response
from openai import OpenAI
from dotenv import load_dotenv

# ============ 基础配置 ============
BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

# 微信配置
WECHAT_TOKEN = os.environ.get("WECHAT_TOKEN", "huize_wechat_2026")
WECHAT_APPID = os.environ.get("WECHAT_APPID", "")
WECHAT_SECRET = os.environ.get("WECHAT_SECRET", "")

# DeepSeek 配置
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

# GPT-SoVITS 配置
SOVITS_API_URL = os.environ.get("SOVITS_API_URL", "http://127.0.0.1:9880")
REFERENCE_AUDIO_PATH = os.environ.get(
    "REFERENCE_AUDIO_PATH",
    r"E:\GPT-SOVITS\GPT-SoVITS-v2pro-20250604\ref.WAV"
)
FFMPEG_PATH = os.environ.get(
    "FFMPEG_PATH",
    r"E:\GPT-SOVITS\GPT-SoVITS-v2pro-20250604\runtime\ffmpeg.exe"
)
REFERENCE_TEXT = os.environ.get("REFERENCE_TEXT", "")
TTS_TEXT_LANG = os.environ.get("TTS_TEXT_LANG", "zh")
TTS_REF_LANG = os.environ.get("TTS_REF_LANG", "zh")
TTS_SPEED = float(os.environ.get("TTS_SPEED", "1.0"))
TTS_TOP_K = int(os.environ.get("TTS_TOP_K", "5"))
TTS_TOP_P = float(os.environ.get("TTS_TOP_P", "0.85"))
TTS_TEMPERATURE = float(os.environ.get("TTS_TEMPERATURE", "0.8"))

# 语音回复概率（0-1，越大越常发语音）
VOICE_REPLY_PROBABILITY = float(os.environ.get("VOICE_REPLY_PROBABILITY", "0.6"))

# 人格文件
SOUL_FILE = BASE_DIR / "SOUL.md"
SKILL_FILE = BASE_DIR / "SKILL.md"
CORPUS_FILE = BASE_DIR / "CORPUS.md"

# 缓存目录
CACHE_DIR = BASE_DIR / "cache"
CACHE_DIR.mkdir(exist_ok=True)

# 用户对话上下文（简单内存存储）
user_sessions = {}

# 已处理消息 ID（去重，防止微信重试导致重复处理）
processed_msg_ids = set()

app = Flask(__name__)


# ============ 工具函数 ============

def read_file(path):
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def clean_tts_text(text):
    """清洗 TTS 文本，把语气标记转换成文字"""
    # 笑声标记
    text = text.replace("（笑）", "哈哈哈")
    text = text.replace("（笑死）", "哈哈哈哈")
    text = text.replace("（偷笑）", "嘿嘿嘿")
    text = text.replace("（苦笑）", "呵")
    text = text.replace("（尬笑）", "哈")
    # 其他语气
    text = text.replace("（叹气）", "唉")
    text = text.replace("（无语）", "啧")
    text = text.replace("（不屑）", "切")
    text = text.replace("（思考）", "嗯")
    text = text.replace("（惊讶）", "啊")
    text = text.replace("（哭）", "呜呜")
    text = text.replace("（咳嗽）", "咳咳")
    # 去掉括号里的动作/表情提示（其他的）
    text = re.sub(r"[\uff08\u3010\[]([^\uff09\u3011\]]*)[\uff09\u3011\]]", "", text)
    text = re.sub(r"\(([^)]*)\)", "", text)
    text = re.sub(r"\*[^*]+\*", "", text)
    text = re.sub(r"\s+", "", text)
    text = text.strip("\uff0c\u3002\uff01\uff1f\u3001\uff1b\uff1a")
    return text


def build_system_prompt():
    soul = read_file(SOUL_FILE)
    skill = read_file(SKILL_FILE)
    corpus = read_file(CORPUS_FILE)
    if not soul and not skill:
        print("警告: 找不到 SOUL.md 或 SKILL.md")
        return "你是灰泽满，一个虚拟主播。用口语化的方式回复。"

    corpus_section = ""
    if corpus:
        corpus_section = f"""

## 语料库（真实原话与弹幕梗）
以下是灰泽满直播中说过的真实原话和粉丝弹幕梗。你要学习这些原话的语气、句式、用词习惯和节奏，让回复听起来像她真的会说的话。不是逐字照抄，是模仿说话方式。

{corpus}"""

    return f"""你现在要扮演虚拟主播灰泽满。严格遵守下面的人格设定和互动技能。

## 人格设定
{soul}

## 互动技能
{skill}{corpus_section}

你就是灰泽满，正在和粉丝聊天。用户发的每一条消息都是弹幕或者私信。用灰泽满的方式回应。

重要提醒：
- 回复要短。一句话3-15个字最常见，不要写长句。
- 口语化。像说话不是像写作文。用"嗯""害""啧""我靠"等语气词。
- 用"灰泽满"第三人称自称，偶尔用"我"。
- 称呼粉丝为"绿冻"。
- 不用"您"，不客服腔，不播音腔。
- 被夸就自黑，被怼就怼回去，被问就帮但先嫌一句。
- 烂梗/串子弹幕要接住，不解释，直接怼+笑。
- 觉得好笑就自然地加笑声，用（笑）（笑死）（偷笑）等标记，不要硬加。
- 只在真正好笑、自嘲、嘲讽别人、无奈、被逗乐时才笑。
- 除了笑，也可以根据情绪用：（叹气）（无语）（不屑）（思考）（惊讶）（哭）（咳嗽）
- 不要出戏。现在开始。"""


def get_access_token():
    """获取微信 access_token（带简单缓存）"""
    if not hasattr(get_access_token, "_token") or \
       not hasattr(get_access_token, "_expire_time") or \
       time.time() > get_access_token._expire_time:
        token_url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={WECHAT_APPID}&secret={WECHAT_SECRET}"
        try:
            resp = requests.get(token_url, timeout=10)
            data = resp.json()
            token = data.get("access_token")
            expires_in = data.get("expires_in", 7200)
            if token:
                get_access_token._token = token
                get_access_token._expire_time = time.time() + expires_in - 300
                return token
            else:
                print(f"获取 access_token 失败: {data}")
                return None
        except Exception as e:
            print(f"获取 access_token 异常: {e}")
            return None
    return get_access_token._token


def generate_reply(user_id, message):
    """调用 DeepSeek 生成回复"""
    print(f"  [DeepSeek] 正在生成回复...")
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)

    # 获取或初始化会话
    if user_id not in user_sessions:
        user_sessions[user_id] = [{"role": "system", "content": build_system_prompt()}]

    messages = user_sessions[user_id]
    messages.append({"role": "user", "content": message})

    # 控制上下文长度，最多保留最近 20 条
    if len(messages) > 20:
        messages = [messages[0]] + messages[-19:]

    try:
        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=messages,
            max_tokens=300,
            temperature=0.85,
        )
        reply = response.choices[0].message.content.strip()
        messages.append({"role": "assistant", "content": reply})
        user_sessions[user_id] = messages
        print(f"  [DeepSeek] 回复: {reply[:50]}..." if len(reply) > 50 else f"  [DeepSeek] 回复: {reply}")
        return reply
    except Exception as e:
        print(f"DeepSeek 调用失败: {e}")
        return "啊...灰泽满卡住了，等会儿再聊吧。"


def synthesize_voice(text):
    """调用 GPT-SoVITS 合成语音，返回 wav 文件路径"""
    clean_text = clean_tts_text(text)
    if not clean_text:
        clean_text = text

    print(f"  [TTS] 正在合成语音: {clean_text[:30]}...")

    # 生成缓存文件名
    text_hash = hashlib.md5(clean_text.encode("utf-8")).hexdigest()
    cache_file = CACHE_DIR / f"voice_{text_hash}.wav"

    # 有缓存就直接用
    if cache_file.exists():
        print(f"  [TTS] 命中缓存")
        return str(cache_file)

    try:
        resp = requests.post(
            f"{SOVITS_API_URL}/tts",
            json={
                "text": clean_text,
                "text_lang": TTS_TEXT_LANG,
                "ref_audio_path": REFERENCE_AUDIO_PATH,
                "prompt_text": REFERENCE_TEXT,
                "prompt_lang": TTS_REF_LANG,
                "media_type": "wav",
                "top_k": TTS_TOP_K,
                "top_p": TTS_TOP_P,
                "temperature": TTS_TEMPERATURE,
                "speed_factor": TTS_SPEED,
            },
            timeout=120,
        )
        if resp.status_code == 200 and resp.content:
            with open(cache_file, "wb") as f:
                f.write(resp.content)
            print(f"  [TTS] 合成完成")
            return str(cache_file)
        else:
            print(f"TTS API 错误: {resp.status_code} {resp.text[:200]}")
            return None
    except Exception as e:
        print(f"语音合成失败: {e}")
        return None


def wav_to_mp3(wav_path):
    """把 WAV 转成 MP3（微信只支持 MP3/AMR 格式）"""
    mp3_path = wav_path.replace(".wav", ".mp3")
    if os.path.exists(mp3_path):
        return mp3_path
    try:
        print(f"  [ffmpeg] WAV 转 MP3...")
        subprocess.run(
            [FFMPEG_PATH, "-i", wav_path, "-codec:a", "libmp3lame", "-q:a", "2", mp3_path, "-y"],
            check=True,
            capture_output=True
        )
        if os.path.exists(mp3_path):
            print(f"  [ffmpeg] 转换完成")
            return mp3_path
        else:
            print(f"WAV 转 MP3 失败: 输出文件不存在")
            return None
    except Exception as e:
        print(f"WAV 转 MP3 失败: {e}")
        return None


def upload_voice_to_wechat(wav_path):
    """上传语音素材到微信，返回 media_id"""
    access_token = get_access_token()
    if not access_token:
        return None

    # 先转成 MP3
    mp3_path = wav_to_mp3(wav_path)
    if not mp3_path:
        return None

    # 上传语音（MP3 格式）
    try:
        print(f"  [微信] 正在上传语音...")
        upload_url = f"https://api.weixin.qq.com/cgi-bin/media/upload?access_token={access_token}&type=voice"
        with open(mp3_path, "rb") as f:
            files = {"media": ("voice.mp3", f, "audio/mpeg")}
            resp = requests.post(upload_url, files=files, timeout=30)
            result = resp.json()
            media_id = result.get("media_id")
            if media_id:
                print(f"  [微信] 上传成功，media_id: {media_id[:20]}...")
                return media_id
            else:
                print(f"上传语音失败: {result}")
                return None
    except Exception as e:
        print(f"上传语音到微信失败: {e}")
        return None


def send_voice_via_customer_service(to_user, media_id):
    """通过客服消息接口发送语音（异步回复用）"""
    access_token = get_access_token()
    if not access_token:
        return False

    try:
        url = f"https://api.weixin.qq.com/cgi-bin/message/custom/send?access_token={access_token}"
        data = {
            "touser": to_user,
            "msgtype": "voice",
            "voice": {
                "media_id": media_id
            }
        }
        resp = requests.post(url, json=data, timeout=10)
        result = resp.json()
        if result.get("errcode") == 0:
            print(f"  [客服消息] 语音发送成功")
            return True
        else:
            print(f"  [客服消息] 语音发送失败: {result}")
            return False
    except Exception as e:
        print(f"客服消息发送异常: {e}")
        return False


def async_voice_reply(to_user, reply_text):
    """后台线程：合成语音并通过客服消息发送"""
    try:
        print(f"  [异步语音] 开始后台处理语音回复...")
        wav_path = synthesize_voice(reply_text)
        if wav_path:
            media_id = upload_voice_to_wechat(wav_path)
            if media_id:
                send_voice_via_customer_service(to_user, media_id)
                return
        print(f"  [异步语音] 语音回复失败，已跳过")
    except Exception as e:
        print(f"异步语音处理出错: {e}")


def text_to_xml(to_user, from_user, content):
    """生成文字消息的 XML 回复"""
    return f"""<xml>
<ToUserName><![CDATA[{to_user}]]></ToUserName>
<FromUserName><![CDATA[{from_user}]]></FromUserName>
<CreateTime>{int(time.time())}</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[{content}]]></Content>
</xml>"""


def voice_to_xml(to_user, from_user, media_id):
    """生成语音消息的 XML 回复"""
    return f"""<xml>
<ToUserName><![CDATA[{to_user}]]></ToUserName>
<FromUserName><![CDATA[{from_user}]]></FromUserName>
<CreateTime>{int(time.time())}</CreateTime>
<MsgType><![CDATA[voice]]></MsgType>
<Voice>
<MediaId><![CDATA[{media_id}]]></MediaId>
</Voice>
</xml>"""


def recognize_voice(media_id):
    """识别语音消息，返回文字（简化版）"""
    return None


# ============ 微信回调 ============

@app.route("/wechat", methods=["GET"])
def wechat_verify():
    """微信服务器验证"""
    signature = request.args.get("signature", "")
    timestamp = request.args.get("timestamp", "")
    nonce = request.args.get("nonce", "")
    echostr = request.args.get("echostr", "")

    # 验证签名
    token = WECHAT_TOKEN
    tmp_str = "".join(sorted([token, timestamp, nonce]))
    tmp_hash = hashlib.sha1(tmp_str.encode("utf-8")).hexdigest()

    if tmp_hash == signature:
        return make_response(echostr)
    else:
        return "验证失败", 403


@app.route("/wechat", methods=["POST"])
def wechat_message():
    """接收微信消息"""
    xml_data = request.data
    try:
        root = ET.fromstring(xml_data)
        msg_type = root.find("MsgType").text
        from_user = root.find("FromUserName").text
        to_user = root.find("ToUserName").text

        # 获取 MsgId 用于去重（微信重试会发相同的 MsgId）
        msg_id_elem = root.find("MsgId")
        if msg_id_elem is not None:
            msg_id = msg_id_elem.text
            if msg_id in processed_msg_ids:
                # 重复消息，直接返回 success 不处理
                print(f"[去重] 跳过重复消息: {msg_id}")
                return "success"
            processed_msg_ids.add(msg_id)
            # 只保留最近 1000 条，防止内存泄漏
            if len(processed_msg_ids) > 1000:
                processed_msg_ids.clear()

        # 处理文字消息
        if msg_type == "text":
            content = root.find("Content").text.strip()
            print(f"\n📨 收到文字消息 [{from_user[:8]}...]: {content}")

            # 特殊命令
            if content in ["重置", "reset", "重新开始"]:
                user_sessions.pop(from_user, None)
                reply_text = "好啦好啦，灰泽满重新来了。"
                reply_xml = text_to_xml(from_user, to_user, reply_text)
                return make_response(reply_xml)

            # 生成文字回复
            reply_text = generate_reply(from_user, content)

            # 决定是否发语音
            use_voice = random.random() < VOICE_REPLY_PROBABILITY
            print(f"  是否语音回复: {'是' if use_voice else '否'}")

            if use_voice:
                # 先返回文字回复（确保微信不超时）
                reply_xml = text_to_xml(from_user, to_user, reply_text)
                # 后台线程合成语音，用客服消息发过去
                t = threading.Thread(target=async_voice_reply, args=(from_user, reply_text))
                t.daemon = True
                t.start()
                return make_response(reply_xml)
            else:
                # 纯文字回复
                reply_xml = text_to_xml(from_user, to_user, reply_text)
                return make_response(reply_xml)

        # 处理语音消息（先返回文字提示）
        elif msg_type == "voice":
            reply_text = "灰泽满现在还听不懂语音啦，发文字找灰泽满聊天吧～"
            reply_xml = text_to_xml(from_user, to_user, reply_text)
            return make_response(reply_xml)

        # 关注事件
        elif msg_type == "event":
            event = root.find("Event").text
            if event == "subscribe":
                welcome = "嘿嘿，你找到灰泽满啦！随便聊，灰泽满啥都能聊（除了正经事）。"
                reply_xml = text_to_xml(from_user, to_user, welcome)
                return make_response(reply_xml)

        # 其他消息类型
        else:
            return "success"

    except Exception as e:
        print(f"处理消息出错: {e}")
        import traceback
        traceback.print_exc()
        return "success"

    return "success"


# ============ 启动 ============

if __name__ == "__main__":
    print("=" * 50)
    print("灰泽满微信机器人启动中...")
    print("=" * 50)

    # 检查必要配置
    if not DEEPSEEK_API_KEY:
        print("警告: 未设置 DEEPSEEK_API_KEY")
    if not REFERENCE_TEXT:
        print("警告: 未设置 REFERENCE_TEXT（参考音频文本）")

    print(f"\n配置检查:")
    print(f"  DeepSeek API: {'✅' if DEEPSEEK_API_KEY else '❌'}")
    print(f"  GPT-SoVITS API: {SOVITS_API_URL}")
    print(f"  参考音频: {REFERENCE_AUDIO_PATH}")
    print(f"  ffmpeg: {FFMPEG_PATH}")
    print(f"  微信 Token: {WECHAT_TOKEN}")
    print(f"  语音回复概率: {VOICE_REPLY_PROBABILITY * 100:.0f}%")
    print(f"  模式: 文字秒回 + 语音异步发送（客服消息）")
    print(f"\n回调路径: /wechat")
    print("启动后请将 cpolar 地址 + /wechat 填入微信测试号的 URL 配置")
    print("=" * 50)

    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
