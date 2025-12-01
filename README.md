# OneBot 11 Bot 说明

## 快速启动

1. 安装依赖：`pip install -r requirements.txt`
2. 根据实际情况修改 `settings.json`（监听/发送端口、IP、白名单、超级管理员、workers）。
3. 启动：`python main.py`

默认监听 `http://127.0.0.1:7654/`，上游 OneBot/NapCat 可向该地址 POST 事件；发送端口由 `settings.json -> send` 指定。

## 目录结构

- `main.py`：读取配置、启动监听服务与工作线程。
- `listen.py`：Flask HTTP 服务，负责接收 JSON 事件并投入队列。
- `message_router.py`：白名单校验、命令解析、分发到插件/管理指令。
- `admin.py`：超级管理员指令处理（`.bot admin ...`）。
- `plugin_loader.py`：自动加载 `plugins/` 下的插件。
- `plugins/`：功能插件目录（示例 `plugins_helloworld.py`）。
- `send.py`：把插件返回的动作 POST 到 OneBot 接口。
- `logger.py`：统一 info/success/error 输出。
- `settings.json`：运行配置；`requirements.txt`：依赖列表。

## 消息处理流程

1. 上游 HTTP POST -> `listen.py`，事件进入线程安全队列。
2. 多个 worker（数量由 `settings.json.workers` 决定）并行读取事件。
3. `message_router.py`：
   - 过滤非 message 事件。
   - 按 group/private 白名单或黑名单策略判定是否继续。
   - 仅解析以 `.bot` 或 `。bot` 开头的消息，去掉前缀后将剩余部分拆分为 `command + params`。
   - `command == "admin"` 时交给 `admin.py`；否则交给插件管理器。
4. 插件或管理员返回的响应列表交由 `send.py`，转换为 `send_group_msg`/`send_private_msg`/`send_msg` 等 API 调用，再 POST 回上游。

## 配置要点（settings.json）

- `group`、`private`：白名单/黑名单。仅含 `"all"` 表示处理所有该类型消息；若同时包含 `"all"` 和其他号码，则表示黑名单模式。
- `superadmin`：允许执行 `.bot admin ...` 的 QQ 号。
- `listen`/`send`：监听端口与发送端口（上游 NapCat 通常 listen=事件上报端口，send=调用动作端口）。
- `workers`：并发处理线程数。

## 编写插件

1. 在 `plugins/` 下新建文件，命名为 `plugins_<功能名>.py`，并确保目录下存在 `__init__.py`。
2. 实现函数：

```python
def handle(command, params, context, settings):
    # command: 指令名(例如 hello)
    # params: 以空格拆分的参数列表
    # context: 来源(group/private)、群号、QQ 号、原始配置等
    # settings: settings.json 的完整内容
    return response_list_or_None
```

3. 返回值必须是列表：列表内每个元素描述一条待发送消息。

```python
return [{
    "type": "send_group_msg",      # 或 send_private_msg / send_msg
    "number": context.get("group_id"),  # 可覆盖默认目标，缺省时主程序会用当前会话
    "text": "hello world!"
}]
```

4. 若返回 `None` 或空列表，表示插件未处理该指令，控制权会继续传给下一个插件。
5. 插件中可自由解析 `params`，甚至根据 `settings` 读取额外配置；必要时也可返回自定义 `payload`，主程序会直接 POST。

示例：`plugins/plugins_helloworld.py` 会在收到 `.bot hello world too!` 时回复 `hello world!`。

## 插件热更新

当前实现会在启动时加载插件，如需新增/修改插件：

1. 按上述命名规则创建/修改文件。
2. 重启 `python main.py` 以重新加载模块。

（可按需扩展成动态加载机制，但默认流程推荐重启。）

## 管理员指令

- 仅 `superadmin` 列表内账号可执行。
- 使用 `.bot admin <sub-command>` 触发，例如 `.bot admin ping`、`.bot admin status`。
- `admin.py` 是专门的处理器，可在其中新增自定义子命令，返回格式与插件一致。

## 日志

- 全局 logger 打印三种级别：`INFO`、`SUCCESS`、`ERROR`。
- 关键节点（接收消息、白名单判定、插件执行、HTTP 调用结果）都会输出，方便在终端或 VS Code OUTPUT 面板中实时观察。

## 常见扩展思路

- 在 `admin.py` 添加更多子命令，例如热加载插件、查看运行状态等。
- 在插件中访问外部 API 或数据库，实现自定义功能。
- 扩展 `send.py` 以支持更多 OneBot 动作（踢人、禁言等），只需在插件返回的字典中设置 `type` 与完整 `payload`。
