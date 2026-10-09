# dsh-desktop-bridge 接口测试

用 GIMBAL 对 [`@ignotuss/dsh-desktop-bridge`](https://github.com/ignotuss/dsh-desktop-bridge)
暴露的回环 HTTP API 做接口测试。该插件跑在 DSH（DeepSeek Harness）桌面端宿主内部，
把 `sessionController` 以 Bearer 令牌保护的形式发布到 `127.0.0.1:<随机端口>`，
端口与令牌写在 `<DSH_HOME>/desktop-bridge.json`。

| 文件 | 作用 |
|---|---|
| `scenario.readonly.json` | 32 步：鉴权 / Origin / Host（DNS 重绑定）/ 路由 / 405 / 入参校验 / 安全响应头。除 `GET /v1/sessions` 与 `GET …/events` 外全部在 controller 之前被拦截，**对真实桌面端无副作用** |
| `scenario.write.json` | 4 步：创建会话、发送消息、回读事件。**会在宿主里启动 agent 并追加一条用户回合** |
| `run.py` | 读 descriptor → 改写 `services.bridge` 为实际端口 → 把 token / port / session_id 写入 `config.vars` → `gimbal run launch` |
| `mock_host.mjs` | 没有桌面端时，用内存版 `sessionController` 挂载**真实的**插件 `apply()`（随机端口、令牌、descriptor、审计日志都是插件本体代码） |

## 对真实 DSH 桌面端

1. 桌面端侧栏 **插件 → 添加插件**，填 `@ignotuss/dsh-desktop-bridge`，选择立即启用。
2. 至少开着一个会话（只读用例要读它的事件）。
3. 运行：

```bash
# 只读 + 负向（默认，安全）
python examples/dsh_desktop_bridge/run.py

# 指定 descriptor / 会话
python examples/dsh_desktop_bridge/run.py \
  --descriptor ~/.dsh/desktop-bridge.json --session-id session-1f0e…

# 写用例：请指定一个测试用会话；--workdir 是新会话的 cwd（必须已存在）
python examples/dsh_desktop_bridge/run.py --write \
  --session-id session-1f0e… --workdir ~/scratch/dsh-probe

# '--' 之后透传给 gimbal run launch
python examples/dsh_desktop_bridge/run.py -- -o json --reporter html
```

注意：

- 插件 `config.allowCreate: false` 时，`POST /v1/sessions` 一律 403，只读用例会停在第一个
  “创建会话：…” 校验步骤（期望 415 实得 403）——这是配置所致，不是缺陷。
- 配了 `cwdAllowlist` 时，`--workdir` 必须落在白名单内。
- 插件每次重载都会换端口和令牌，`run.py` 每次都会重新读 descriptor。

## 无桌面端时（CI / 本地自测）

```bash
git clone https://github.com/ignotuss/dsh-desktop-bridge /tmp/dsh-desktop-bridge
export DSH_HOME=$(mktemp -d)
BRIDGE_DIR=/tmp/dsh-desktop-bridge node examples/dsh_desktop_bridge/mock_host.mjs &
python examples/dsh_desktop_bridge/run.py --write
kill %1     # 插件卸载时会删除 descriptor
```

需要 Node.js ≥ 20。`mock_host.mjs` 预置一个会话；`BRIDGE_ALLOW_CREATE=false`、
`BRIDGE_CWD_ALLOWLIST=a:b` 可模拟插件的两项配置。

## 已知限制（来自当前 GIMBAL 构建）

- `config.services` 与 `api.path` 只在预处理阶段静态展开，`extract` 出的值进不了
  后续步骤的 URL 路径。所以写用例里新建会话的 id 只做断言，发消息走 `--session-id`
  指定的会话。
- `gimbal run launch` 暂无 `--var`，变量由 `run.py` 写进渲染后的临时场景文件（跑完即删）。
- 场景在第一个失败步骤处停止；后续步骤不再执行，修复后需重跑。
