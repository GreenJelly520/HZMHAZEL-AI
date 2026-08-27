# 灰泽满微信机器人

基于 GPT-SoVITS + DeepSeek + 微信公众号测试号的 VTuber 语音对话机器人。扮演虚拟主播灰泽满的人格，支持文字和语音回复。

## ✨ 功能特性

- 🎙️ **GPT-SoVITS 语音合成** — 基于训练好的声音模型生成个性化语音
- 🤖 **DeepSeek 对话生成** — 带人格设定的 AI 对话，支持上下文记忆
- 💬 **微信公众号接入** — 通过测试号实现微信内聊天
- 🎭 **完整人格设定** — SOUL（性格）+ SKILL（互动技巧）+ CORPUS（语料梗库）三层设定
- 🔊 **语音异步发送** — 文字秒回，语音后台合成后通过客服消息推送，不超时
- 🗑️ **消息去重** — 自动处理微信重试消息，不重复回复
- 💾 **语音缓存** — 相同文本自动复用缓存，减少重复合成

## 📋 前置要求

- Python 3.8+
- [GPT-SoVITS v2](https://github.com/RVC-Boss/GPT-SoVITS) — 已训练好的模型 + API 服务
- [DeepSeek API Key](https://platform.deepseek.com/)
- 微信公众号测试号（[申请地址](https://mp.weixin.qq.com/debug/cgi-bin/sandbox?t=sandbox/login)）
- 内网穿透工具（cpolar / ngrok / frp 等）

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env`，填入你的配置：

```bash
cp .env.example .env
```

需要配置的关键项：
- `WECHAT_TOKEN` — 微信回调 Token（自己随便设，和后台一致就行）
- `WECHAT_APPID` / `WECHAT_SECRET` — 微信测试号的凭证
- `DEEPSEEK_API_KEY` — DeepSeek API Key
- `SOVITS_API_URL` — GPT-SoVITS API 地址（默认 http://127.0.0.1:9880）
- `REFERENCE_AUDIO_PATH` / `REFERENCE_TEXT` — 参考音频路径和文本
- `FFMPEG_PATH` — ffmpeg 可执行文件路径

### 3. 启动 GPT-SoVITS API

```bash
cd 你的GPT-SoVITS目录
runtime\python.exe api_v2.py -a 127.0.0.1 -p 9880
```

### 4. 启动机器人

```bash
python wechat_bot.py
```

### 5. 内网穿透（cpolar 为例）

```bash
cpolar http 5000
```

记下 https 的公网地址。

### 6. 配置微信测试号

在微信测试号后台填写：

| 字段 | 值 |
|------|-----|
| URL | `https://你的cpolar域名/wechat` |
| Token | 和 `.env` 里的 `WECHAT_TOKEN` 一致 |

提交验证成功后，扫码关注测试号即可开始聊天。

## 🎮 使用说明

### 基本使用
- 关注测试号后直接发文字消息聊天
- 60% 概率收到语音回复（先文字后语音，异步推送）
- 语音通过客服消息发送，可能延迟几秒

### 特殊命令
| 命令 | 功能 |
|------|------|
| `重置` / `reset` / `重新开始` | 清空对话上下文 |

## 📁 项目结构

```
wechat_bot/
├── wechat_bot.py      # 主程序
├── .env.example       # 配置模板
├── .gitignore         # Git 忽略规则
├── requirements.txt   # Python 依赖
├── SOUL.md            # 人格设定（性格底色、价值观、说话风格）
├── SKILL.md           # 互动技能（7维互动分流、语气词指南）
├── CORPUS.md          # 语料库（原声原话、烂梗库、回复模板）
├── README.md          # 项目说明
└── cache/             # 语音缓存（自动生成，已 gitignore）
```

## ⚙️ 配置说明

### 语音回复概率

```env
VOICE_REPLY_PROBABILITY=0.6  # 0.6 = 60% 概率发语音
```

### TTS 参数调优

```env
TTS_SPEED=1.0        # 语速，1.0 正常
TTS_TEMPERATURE=0.8  # 多样性，越高越随机
TTS_TOP_P=0.85       # 核采样参数
TTS_TOP_K=5          # Top-K 采样参数
```

## 🧠 人格系统

采用三层设定架构：

- **SOUL.md** — 灵魂层：核心身份、性格底色、价值观、情绪光谱
- **SKILL.md** — 技能层：7维互动分流、5个锚定场景、语气词使用指南
- **CORPUS.md** — 语料层：原声原话、烂梗库、回复模板参考

AI 对话时会加载这三个文件，生成符合人设的回复。

## 📝 注意事项

- 微信测试号仅供开发测试使用，生产环境请使用正式公众号
- 免费版 cpolar 重启后地址会变，需要更新微信后台配置
- 语音合成需要 GPU，CPU 会非常慢
- 请勿用于商业用途，遵守相关法律法规

## 📄 许可证

MIT License
