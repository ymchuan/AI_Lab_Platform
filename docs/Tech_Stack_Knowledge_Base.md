# 技术栈知识手册

> 边做边学，每用到一个新技术就记录下来。既是学习笔记，也是面试准备材料。

---

## 1. LM Studio

### 是什么

一个桌面应用，让你在本地电脑上运行和管理大语言模型（LLM）。类似一个"大模型播放器"。

### 为什么用它

- 一键下载模型（不用自己找 GGUF 文件）
- 自带图形界面，可以聊天测试
- 自动开启 OpenAI Compatible API，不用写代码就能对外提供服务
- 支持 RTX 5090 等消费级 GPU 加速推理

### 核心概念

```text
Server Running = ON          → 启动本地 API 服务
Serve on Local Network = ON  → 允许局域网其他设备访问
Require Authentication = OFF → 不需要密码（生产环境应该开）
OpenAI Compatible API        → 暴露 /v1/chat/completions 等接口
```

### 类比

可以把 LM Studio 理解为"大模型的本地服务器"，就像：

- Nginx 是网页服务器
- MySQL 是数据库服务器
- **LM Studio 是大模型推理服务器**

---

## 2. OpenAI Compatible API

### 是什么

一套标准的 API 接口规范，由 OpenAI 定义。其他厂商/工具可以兼容这套接口。

### 为什么要兼容

```text
如果不兼容：
  每个模型厂商都定义自己的 API → 客户端要写 N 套代码

如果都兼容 OpenAI：
  客户端只需要写一套代码 → 换模型只改 Base URL
```

### 核心接口

```text
POST /v1/chat/completions    → 聊天补全（最常用）
POST /v1/completions         → 文本补全（旧版）
POST /v1/embeddings          → 文本向量化
GET  /v1/models              → 获取模型列表
```

### 类比

```text
USB 接口 → 不同设备都能用同一个 USB 口充电/传数据
OpenAI API → 不同模型都能用同一个接口调用
```

### 你的项目中的角色

```text
5090 LM Studio 提供 OpenAI Compatible API
    ↓
LiteLLM 也是 OpenAI Compatible API
    ↓
Cline / OpenWebUI / 其他客户端调用 OpenAI API
    ↓
所有组件都用同一套接口通信
```

---

## 3. LiteLLM

### 是什么

一个 **AI API 网关 / 代理服务器**。它接收客户端的 OpenAI 格式请求，然后转发给后端的实际模型服务。

### 为什么需要它

```text
没有 LiteLLM：
  客户端 → 直接连 LM Studio（只能本机/局域网）
  
有 LiteLLM：
  客户端 → LiteLLM（公网，带 API Key，多模型）→ LM Studio
```

LiteLLM 解决的问题：

1. **统一入口** — 一个端口暴露所有模型
2. **API Key 认证** — 控制谁能访问
3. **模型别名** — 给模型起好记的名字（`qwen-local`）
4. **多后端** — 后面可以接 LM Studio、vLLM、Ollama、OpenAI、Claude 等
5. **负载均衡** — 多个相同模型时可以分发请求
6. **日志和监控** — 记录每次调用

### 核心配置

```yaml
model_list:
  - model_name: qwen-local          # 对外暴露的模型名
    litellm_params:
      model: openai/qwen/qwen3.6-27b
      api_base: http://127.0.0.1:12340/v1  # 后端地址
      api_key: lm-studio              # 后端的 key

general_settings:
  master_key: <LABAGENT_API_KEY>    # 对外的 API Key
```

### 类比

```text
LiteLLM ≈ Nginx（但专门给 AI API 用）

Nginx：  浏览器 → Nginx → 后端 Web 服务器
LiteLLM：客户端 → LiteLLM → 后端大模型服务
```

### 官网

```text
https://docs.litellm.ai/
```

---

## 4. SSH Reverse Tunnel（SSH 反向隧道）

### 是什么

SSH 的一个功能，可以让远程服务器"反向"访问你本机的服务。

### 为什么需要它

```text
你的 5090 在校园网内网（172.16.14.240）
云服务器有公网 IP（82.156.69.153）

正常情况：
  云服务器 → 172.16.14.240:1234  ❌ 不通（内网不可达）

用反向隧道：
  5090 主动连到云服务器 → 建立隧道
  云服务器访问自己 12340 端口 → 通过隧道 → 转发到 5090:1234  ✅
```

### 命令解析

```bash
ssh -N -R 12340:127.0.0.1:1234 ubuntu@82.156.69.153
```

```text
ssh        → SSH 客户端
-N         → 不执行远程命令，只做转发
-R         → 反向隧道模式
12340      → 云服务器上的监听端口
127.0.0.1  → 转发到 5090 本机的...
1234       → ...LM Studio 端口
ubuntu@82.156.69.153 → 云服务器地址
```

### 类比

```text
正常 SSH：你在家里 → 连到公司的电脑（远程桌面）
反向隧道：你在公司 → 主动连到家里的电脑 → 家里的电脑开了一扇门
                    → 任何人通过公司的这扇门 → 就能访问你家里的服务
```

### 心跳保活参数

```bash
-o ServerAliveInterval=60    # 每60秒发心跳包
-o ServerAliveCountMax=3     # 3次没回应才断开
-o ConnectTimeout=10         # 连接超时10秒
```

没有心跳的话，SSH 连接空闲一段时间会被网络设备（路由器、防火墙）自动断开。

---

## 5. systemd

### 是什么

Linux 系统的**服务管理器**。可以让你的程序在后台运行、开机自启、崩溃自动重启。

### 为什么需要它

```text
手动启动：  你开终端 → 执行命令 → 终端关了程序就停了
systemd：  系统帮你管 → 后台运行 → 开机自启 → 崩溃重启
```

### 核心概念

```text
.service 文件  → 定义一个服务（叫什么、怎么启动、怎么重启）
daemon-reload  → 重新加载服务配置
enable         → 开机自启
start/stop     → 启动/停止
status         → 查看状态
journalctl     → 查看日志
```

### 服务文件结构

```ini
[Unit]           → 描述和依赖
[Service]        → 启动方式
  ExecStart      → 启动命令
  Restart=always → 崩溃自动重启
  RestartSec=5   → 5秒后重试
[Install]        → 开机自启配置
```

### 类比

```text
Windows 服务（services.msc）→ systemd 在 Linux 上的对应物
```

---

## 6. SSH 密钥认证

### 是什么

用一对密钥（公钥 + 私钥）代替密码登录 SSH。

### 为什么需要它

```text
密码登录：  每次都要输入密码 → 自动化脚本不方便
密钥登录：  配好一次 → 以后自动认证 → 不用输密码
```

### 原理

```text
5090 本机保存：私钥（id_ed25519）       → 绝对不能泄露
云服务器保存：公钥（id_ed25519.pub）    → 可以公开

认证过程：
  5090 说："我有私钥"
  云服务器说："验证一下" → 用公钥加密一个消息 → 发给 5090
  5090 用私钥解密 → 回复
  云服务器确认 → 登录成功
```

### 配置步骤（每台新机器都要做一次）

```bash
# 1. 生成密钥（一路回车，不设密码）
ssh-keygen -t ed25519

# 2. 传公钥到目标服务器（会要求输入一次密码）
# Windows PowerShell:
type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh ubuntu@服务器IP "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"

# Linux/Mac:
ssh-copy-id ubuntu@服务器IP

# 3. 测试免密登录
ssh ubuntu@服务器IP "echo ok"
# 返回 ok 且无密码提示 = 成功
```

### 注意事项

- 每台新电脑（5090、David 个人机、笔记本等）都要单独生成密钥并上传
- 私钥不能泄露，公钥可以随便传
- 云服务器的 `~/.ssh/authorized_keys` 可以放多个公钥，允许多台机器免密登录

### ed25519 vs RSA

```text
ed25519 → 更短、更快、更安全（推荐）
RSA     → 老牌算法，兼容性好但密钥更长
```

---

## 7. Docker

### 是什么

一个**容器化平台**，可以把应用和它的所有依赖打包成一个"容器"，在任何地方运行。

### 为什么需要它

```text
不用 Docker：
  装依赖 → 版本冲突 → "在我机器上能跑" → 换台机器就挂

用 Docker：
  打包成镜像 → 在任何有 Docker 的机器上都能跑 → 环境一致
```

### 核心概念

```text
镜像（Image）    → 打包好的应用模板（只读）
容器（Container）→ 运行中的镜像实例（可读写）
端口映射         → 容器内部端口映射到宿主机端口
卷（Volume）     → 持久化数据，容器删了数据还在
```

### 常用命令

```bash
docker run -d --name xxx   # 后台运行容器
docker ps                  # 查看运行中的容器
docker logs xxx            # 查看日志
docker stop xxx            # 停止容器
docker rm xxx              # 删除容器
docker pull xxx            # 拉取镜像
```

### 类比

```text
虚拟机 → 完整的操作系统，重，慢
Docker → 只打包应用层，轻，快
```

---

## 8. OpenWebUI

### 是什么

一个开源的 **Web 聊天界面**，类似 ChatGPT 的网页版，但连接的是你自己的模型。

### 为什么需要它

```text
只有 Cline → 只能在 VS Code 里用 → 演示不方便
有 OpenWebUI → 打开浏览器就能用 → 演示效果好 → 多人可用
```

### 功能

- 类 ChatGPT 的聊天界面
- 支持多模型切换
- 文件上传（PDF、图片等）
- 会话历史保存
- 多用户支持
- RAG 知识库（后续可以加）

### 部署方式

```bash
docker run -d \
  --name open-webui \
  -p 3000:8080 \
  -e OPENAI_API_BASE_URL=http://127.0.0.1:8000/v1 \
  -e OPENAI_API_KEY=xxx \
  -v open-webui:/app/backend/data \
  --restart always \
  ghcr.io/open-webui/open-webui:main
```

---

## 9. Cline

### 是什么

VS Code 的一个 AI 编程助手插件，支持 Agent 模式（能自动读文件、写代码、跑命令）。

### 和其他插件的区别

```text
GitHub Copilot   → 代码补全为主（Tab 补全）
Continue         → 代码补全 + 聊天
Cline            → Agent 模式，能自主完成多步任务
Cursor           → 独立 IDE，内置 AI
```

### Agent 模式

```text
普通聊天：  你问一句 → AI 答一句
Agent 模式：你给一个目标 → AI 自己规划步骤 → 读代码 → 写代码 → 跑命令 → 完成任务
```

### 支持 OpenAI Compatible API

Cline 可以配置任何 OpenAI 兼容的后端，不只是 Claude。这就是我们能用它连接本地 Qwen 的原因。

---

## 10. NAT（Network Address Translation）

### 是什么

网络地址转换。让内网多台设备共享一个公网 IP 上网。

### 为什么存在

```text
公网 IPv4 不够用 → 不是每台设备都能有公网 IP
NAT 解决：内网设备用私有 IP → 通过路由器/NAT 设备共享一个公网 IP
```

### 对你项目的影响

```text
5090 的 IP：172.16.14.240（私有 IP，内网可见）
校园网出口：123.127.159.1（公网 IP，外部可见）

外部 → 123.127.159.1 → 校园网 NAT → 不知道该转发给谁 → 172.16.14.240 收不到
```

这就是为什么需要 SSH Reverse Tunnel。

---

## 11. API Gateway（API 网关）

### 是什么

所有 API 请求的统一入口，负责认证、路由、限流、日志等。

### 为什么需要它

```text
没有网关：
  客户端 A → 模型服务 A
  客户端 B → 模型服务 B
  （混乱，难以管理）

有网关：
  所有客户端 → API Gateway → 路由到对应服务
  （统一认证、统一监控、统一限流）
```

### 你的项目中的网关层级

```text
第一层：LiteLLM（当前）
  - API Key 认证
  - 模型路由
  - OpenAI Compatible API

第二层：Nginx（后续）
  - HTTPS 加密
  - 域名
  - 负载均衡
  - 访问日志
  - 限流
```

---

## 12. RAG（Retrieval-Augmented Generation）— 待实现

### 是什么

检索增强生成。让大模型在回答问题时，先从知识库中检索相关文档，再基于检索结果生成回答。

### 为什么需要它

```text
没有 RAG：
  大模型只知道自己训练时学到的知识 → 不知道你公司的文档

有 RAG：
  用户提问 → 先检索相关文档 → 把文档 + 问题一起给大模型 → 回答基于你的数据
```

### 流程

```text
1. 文档 → 切分成小块（Chunking）
2. 每块 → Embedding 模型 → 生成向量
3. 向量 → 存入向量数据库
4. 用户提问 → 生成问句向量 → 在向量库中搜索相似内容
5. 相关文档 + 问题 → 大模型 → 生成回答
```

### 核心组件

```text
Embedding 模型  → 把文本变成数字向量（待部署到新设备；8060S 当前不可用）
向量数据库      → 存储和搜索向量（ChromaDB / Qdrant）
文档分块        → 把长文档切成适合检索的小块
检索策略        → 找到最相关的文档片段
```

新设备的 RTX 5080 16GB + RTX 4060 Ti 16GB 是 32GB 专用显存资源池，但不是单个连续 32GB 显存；Windows shared GPU memory 不能按 VRAM 使用。Embedding / Reranker / VL / 第二推理模型更适合按不同 GPU 分配，跨卡跑单个大模型要单独验证推理引擎支持。

---

## 13. Agent — 待实现

### 是什么

能自主规划和执行多步任务的 AI 系统。不只是回答问题，而是"做事"。

### 和普通聊天的区别

```text
普通聊天：  "Python 怎么读文件？" → 给你一段代码
Agent：     "帮我重构这个项目" → 自己读代码 → 规划步骤 → 修改文件 → 跑测试 → 检查结果
```

### Agent 的核心循环

```text
思考（Reasoning）→ 决定用哪个工具 → 执行（Acting）→ 观察结果 → 继续思考...
```

### 常见 Agent 框架

```text
LangGraph   → LangChain 团队出品，基于图的 Agent 编排
LlamaIndex  → 专注 RAG + Agent
CrewAI      → 多 Agent 协作
AutoGen     → 微软出品，多 Agent 对话
```

---

## 14. MCP（Model Context Protocol）— 待实现

### 是什么

Anthropic 推出的协议，让 AI 模型可以调用外部工具和资源。

### 为什么重要

```text
没有 MCP：
  每个 AI 工具自己定义怎么调用外部服务 → 碎片化

有 MCP：
  统一协议 → 任何 AI 客户端都能调用任何 MCP Server
```

### 在你项目中的应用

```text
你可以写一个 MCP Server：
  → 暴露你的本地模型能力
  → 暴露你的知识库
  → 暴露你的工具（搜索、文件操作等）

然后 Claude Code / Cursor 等客户端可以像调用内置工具一样调用它们
```

---

## 15. vLLM

### 是什么

一个高性能的 LLM 推理和服务引擎，专为生产环境设计。

### 和 LM Studio 的区别

```text
LM Studio  → 桌面应用，个人用，单模型，简单 API
vLLM        → 服务引擎，生产用，多模型，高性能 API
```

### 核心技术

```text
PagedAttention     → 显存管理更高效，同样显存能服务更多请求
Continuous Batching → 多个请求合并处理，吞吐量大幅提升
Tensor Parallelism  → 多 GPU 并行推理
OpenAI Compatible   → 完整兼容 OpenAI API 格式
```

### 为什么后期要换 vLLM

```text
LM Studio 的问题：
  - 一次只能加载一个模型
  - 并发请求处理差
  - 不适合多用户同时使用
  - 没有 Docker 容器化支持

vLLM 的优势：
  - 多模型切换
  - 高并发（Continuous Batching）
  - Docker 部署
  - 适合平台化
  - 性能优化更好（PagedAttention）
```

### 安装方式

```text
Linux:   pip install vllm
Windows: 需要 WSL2 或 Docker
Docker:  docker run vllm/vllm-openai
```

### 5090 上的推荐配置

```text
第一轮候选：Qwen3.6-35B-A3B / Qwen3-Coder-30B-A3B / GLM-4.7-Flash
部署方式：先用 LM Studio 或 llama.cpp 的 GGUF 量化版本验证，再比较 vLLM / SGLang
评测重点：首 token 延迟、tokens/s、显存占用、长上下文、Agent 任务通过率
```

