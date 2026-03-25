# TodoSkill LangGraph Web

这是一个本地运行的多模态 Todo Web 工具，使用 Python + LangGraph 编排，并通过本机 `LM Studio` 提供的 OpenAI 兼容接口调用本地模型。

## 功能

- 通过 Web 页面用中文对话
- 支持文本 + 图片输入
- 把请求路由为待办操作：`create/list/get/update/delete/done/reopen/search`
- 与任务共用同一个 SQLite 数据库
- 额外保存每轮问答的标题、时间、用户消息、助手回复、图片路径和意图

## 目录

- `app/`：后端代码
- `templates/`：页面模板
- `static/`：样式文件
- `uploads/`：上传图片目录
- `data/`：SQLite 数据库目录

## 安装

```bash
cd /Users/zhishikaishi/Desktop/temp/smallTools/TodoSkill
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

默认使用当前项目自己的数据库：

`/Users/zhishikaishi/Desktop/temp/smallTools/TodoSkill/data/todo_agent.db`

如果你之前在旧的 OpenClaw todo 数据库里已有历史任务，可以先迁移到这个新库，然后以后统一只操作这个文件。聊天记录表 `chat_logs` 也会写在这个新库里。

## 运行

```bash
cd /Users/zhishikaishi/Desktop/temp/smallTools/TodoSkill
source .venv/bin/activate
python main.py
```

启动后访问：`http://127.0.0.1:8000`

## 默认模型配置

- 推理后端：`LM Studio`
- 默认接口地址：`http://127.0.0.1:1234`
- 默认模型名：`qwen3.5-4b`

如果你在 LM Studio 里加载的是其他模型，请改 `.env` 里的 `LM_STUDIO_MODEL`。
如果你的 LM Studio API 端口不是默认值，请改 `LM_STUDIO_BASE_URL`。

示例：

```bash
LM_STUDIO_BASE_URL=http://127.0.0.1:1234
LM_STUDIO_MODEL=qwen3.5-4b
LM_STUDIO_TIMEOUT=120
```

## 数据表

### tasks

- `id`
- `title`
- `status`
- `created_at`
- `completed_at`
- `duration`

### chat_logs

- `id`
- `title`
- `user_message`
- `assistant_message`
- `intent`
- `image_path`
- `created_at`
