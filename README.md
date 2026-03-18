# ShopMate

ShopMate 是一个面向电商客服场景的 Agent Demo，重点展示了 `LangChain / LangGraph + Agent 工程化` 的完整落地方式。

这个项目不是一个单纯的问答机器人，而是一个带有：

- 注册登录与登录态管理
- 多会话聊天产品界面
- 工作流编排
- 向量检索
- 多轮会话记忆
- 订单查询工具
- 售后规则判断
- 人工转单机制

的完整客服 Agent 系统。

## 这个项目解决什么问题

在真实电商客服场景里，用户的问题通常不是一句 FAQ 就能解决的，而是会混合这些类型：

- 商品咨询：某个商品适不适合跑步、和另一个型号有什么区别
- 物流查询：订单到哪了、什么时候签收、快递单号是什么
- 售后咨询：能不能退货、是否满足 7 天无理由、退款到哪一步了
- 投诉升级：用户要求赔偿、投诉、人工介入

所以这个项目的目标是：

- 登录后自动识别当前用户
- 新建对话时自动创建 session
- 能区分问题类型
- 能在需要时调用订单查询工具
- 能从 Milvus 检索知识库内容
- 能记住上一轮对话上下文
- 能在风险场景下自动转人工

## 技术栈

- 后端：`FastAPI`、`LangChain`、`LangGraph`、`SQLAlchemy`
- 模型：`qwen3-max`、`text-embedding-v4`
- 向量数据库：`Milvus`
- 存储：`MySQL`、`Redis`
- 认证：`JWT + HttpOnly Cookie`
- 前端：`Next.js`、`React`、`TypeScript`
- 部署：`Docker Compose`

## 核心功能

- 登录注册：支持邮箱注册、登录、退出和当前用户恢复
- 多会话聊天：支持新建对话、历史会话列表、会话切换
- 商品知识问答：从商品资料、FAQ、售后规则中检索答案，并返回引用来源
- 物流查询：识别订单号，查询订单状态和物流信息
- 售后判断：根据签收时间、订单状态判断是否满足退换货条件
- 双层记忆：Redis 保存短期上下文，MySQL 保存完整会话历史
- 人工转单：投诉、赔付、高风险场景自动生成工单
- 调试展示：前端可以查看工单列表、会话详情和记忆恢复结果

## 系统架构

你可以把整个项目理解成 5 层：

1. 前端展示层：负责登录页、会话侧边栏、聊天输入、工单和调试数据展示
2. API 接口层：负责接收 HTTP 请求、登录态恢复、参数校验和统一返回结构
3. Agent 工作流层：真正的核心，负责把一条用户消息拆成多个步骤执行
4. 工具与服务层：提供鉴权、记忆、检索、订单查询、策略判断、大模型调用等能力
5. 存储层：MySQL、Redis、Milvus 分别保存不同类型的数据

可以把调用链路理解为：

```text
用户
  -> 登录后由 Cookie 自动恢复当前用户
  -> 前端 Next.js
  -> FastAPI /api/chat
  -> LangGraph 工作流
     -> Redis 读取短期记忆
     -> MySQL 补全长期历史
     -> Qwen3-Max 识别意图 / 组织回复
     -> Milvus 检索商品、FAQ、政策
     -> MySQL 查询订单、保存消息、保存快照、生成工单
  -> 返回给前端展示
```

## Docker Compose 启动了什么

`docker-compose.yml` 一共会启动这些服务：

- `mysql`：保存订单、会话、消息、工单、状态快照等结构化数据
- `redis`：保存短期会话记忆，提升多轮对话体验
- `etcd`：Milvus 的底层元数据依赖
- `minio`：Milvus 的对象存储依赖
- `milvus`：向量数据库，负责商品、FAQ、政策文档的相似度检索
- `backend`：FastAPI + LangGraph 的后端服务
- `frontend`：Next.js 前端演示界面

也就是说，本地跑起来以后，你其实拿到的是一套完整的小型客服系统，而不是一个单进程脚本。

## 演示账号

项目启动后会自动初始化两个本地演示账号：

- `demo@shopmate.local / demo123456`
- `campus@shopmate.local / campus123456`

推荐直接使用 `demo@shopmate.local` 登录，它关联了更多示例订单和会话数据。

## 一条消息是怎么流转的

下面用用户发一句“帮我查一下 ORD-10002 到哪了”为例说明：

1. 用户登录后，前端从 Cookie 自动恢复当前身份
2. 前端把消息发给 `POST /api/chat`
3. `routes.py` 接收请求后，从登录态中恢复当前用户，再把参数交给 `workflow.py`
4. `load_memory` 先从 Redis 读取这个会话最近的上下文
5. 如果 Redis 没命中，`memory.py` 会去 MySQL 读取历史消息和最新快照
6. `intent_router` 判断这句话属于物流查询，并尝试提取订单号
7. 因为已经提取到 `ORD-10002`，所以不需要 `collect_missing_info`
8. 流程进入 `query_order_tool`，从 MySQL 查询订单和物流状态
9. `response_generator` 把订单信息交给模型，组织出自然语言回复
10. `risk_guard` 判断这条消息是否涉及投诉、赔付或低置信度
11. `persist_memory` 把本轮用户消息、模型回复、状态快照写入 MySQL 和 Redis
12. 如果需要人工介入，再进入 `handoff_ticket` 创建工单
13. 最终把回复、意图、引用、工具调用信息返回给前端

如果用户问的是“这个耳机适合跑步吗”，流程就会从 `intent_router` 走到 `retrieve_from_milvus`，去知识库检索文档，而不是去查订单。

## LangGraph 节点分别是干什么的

`backend/app/graph/workflow.py` 是整个项目最核心的文件，里面把 Agent 拆成了几个节点：

- `load_memory`：加载会话上下文，优先 Redis，失败时回放 MySQL
- `intent_router`：识别当前用户意图，并尝试提取订单号等槽位
- `collect_missing_info`：订单类问题缺少订单号时，先追问用户补充信息
- `retrieve_from_milvus`：从 Milvus 检索商品、FAQ、政策文档
- `query_order_tool`：查询订单详情、物流状态、退款状态
- `policy_checker`：判断是否满足退换货规则
- `response_generator`：根据上下文生成客服回复
- `risk_guard`：检查赔付、投诉、低置信度等风险场景
- `persist_memory`：把本轮对话写回 Redis 和 MySQL
- `handoff_ticket`：创建人工工单

你可以把它理解为“把 Agent 的脑子拆成一条可追踪、可调试、可扩展的流程图”。

## 数据是怎么分工存储的

这部分很重要，因为它决定了不同类型的数据应该如何协作。

### MySQL 存什么

MySQL 存长期且结构化的数据：

- 商品数据
- 订单数据
- 聊天会话
- 聊天消息
- 状态快照
- 人工工单

MySQL 是系统里的“事实来源”。  
比如订单状态、退款状态、工单记录，最终都应该以 MySQL 为准。

### Redis 存什么

Redis 存短期运行态数据：

- 最近几轮对话
- 当前意图
- 已提取槽位
- 当前摘要

它的作用是让下一轮对话更快拿到上下文，而不是保存最终事实。

### Milvus 存什么

Milvus 存向量化后的知识库文档：

- 商品介绍
- FAQ
- 售后政策

当用户问商品信息、政策规则这类问题时，系统会先去 Milvus 找相关文档，再把结果交给模型组织答案。

## 这个项目里“大模型”和“规则”怎么配合

这里不是所有事情都交给大模型做，而是“模型 + 规则 + 工具”组合：

- 大模型负责：意图识别、回复生成、摘要生成
- 规则负责：订单号提取、风险词识别、低成本兜底
- 工具负责：查订单、查商品、创建工单
- 政策函数负责：退换货资格判断

这样设计的原因是：

- 订单和退款这种事实问题不能只靠模型猜
- 售后规则判断最好是确定性逻辑
- 风险场景需要稳定可控

这也是这个项目比“套个聊天接口”更像工程项目的地方。

## 你应该先看哪些文件

如果你想最快看懂整个项目，建议按这个顺序读：

1. [README.md](/d:/code/agent/README.md)
   先理解系统整体结构、存储分工和模块关系。
2. [backend/app/main.py](/d:/code/agent/backend/app/main.py)
   看后端应用是怎么启动的，服务容器是怎么组装的。
3. [backend/app/api/routes.py](/d:/code/agent/backend/app/api/routes.py)
   看外部接口有哪些，以及接口最终把请求交给了谁。
4. [backend/app/graph/workflow.py](/d:/code/agent/backend/app/graph/workflow.py)
   看 Agent 主流程，这是整个项目最关键的地方。
5. [backend/app/services/memory.py](/d:/code/agent/backend/app/services/memory.py)
   看 Redis 和 MySQL 是怎么配合管理记忆的。
6. [backend/app/services/milvus_store.py](/d:/code/agent/backend/app/services/milvus_store.py)
   看知识库是怎么写入和检索的。
7. [backend/app/repositories/store.py](/d:/code/agent/backend/app/repositories/store.py)
   看数据库查询和持久化细节。
8. [backend/app/services/llm.py](/d:/code/agent/backend/app/services/llm.py)
   看模型调用和 mock 模式是怎么封装的。
9. [frontend/components/chat-workspace.tsx](/d:/code/agent/frontend/components/chat-workspace.tsx)
   看前端聊天页面如何调用后端并展示结果。

如果你想快速理解这个项目，其实只要把上面这 9 个文件看清楚，就已经能建立起完整的系统认知。

## 项目目录树

下面这份目录树只保留“需要你真正维护”的文件。

不会展开这些自动生成或依赖目录：

- `.venv/`
- `.pytest_cache/`
- `__pycache__/`
- `frontend/node_modules/`
- `frontend/.next/`

```text
agent/
|-- .env                                      # 本地运行时环境变量，开发时真实读取的是它
|-- .env.example                              # 环境变量模板，给新环境初始化时使用
|-- .gitignore                                # Git 忽略规则
|-- docker-compose.yml                        # 一键启动 MySQL、Redis、Milvus、后端、前端的容器编排文件
|-- README.md                                 # 项目总说明，包含技术栈、目录结构、启动方式和接口说明
|
|-- backend/
|   |-- Dockerfile                            # 后端镜像构建文件
|   |-- README.md                             # 后端补充说明文档
|   |-- pyproject.toml                        # Python 项目配置和依赖声明
|   |-- uv.lock                               # Python 依赖锁文件，保证环境可复现
|   |
|   |-- app/
|   |   |-- __init__.py                       # 将 app 目录声明为 Python 包
|   |   |-- main.py                           # FastAPI 应用入口，负责创建应用、注册路由和启动初始化逻辑
|   |   |
|   |   |-- api/
|   |   |   |-- __init__.py                   # API 包标记文件
|   |   |   `-- routes.py                     # 所有 HTTP 接口定义，包含认证、聊天、会话、工单、重建记忆、重建索引等接口
|   |   |
|   |   |-- core/
|   |   |   |-- __init__.py                   # core 包标记文件
|   |   |   `-- config.py                     # 统一读取环境变量和系统配置，比如模型名、数据库地址、Milvus 配置等
|   |   |
|   |   |-- data/
|   |   |   `-- seed_data.py                  # 演示用种子数据，包含商品、FAQ、政策文档和模拟订单
|   |   |
|   |   |-- db/
|   |   |   |-- __init__.py                   # db 包标记文件
|   |   |   `-- session.py                    # SQLAlchemy 的 Engine、Session、Base 和数据库依赖注入
|   |   |
|   |   |-- graph/
|   |   |   |-- __init__.py                   # graph 包标记文件
|   |   |   |-- state.py                      # LangGraph 运行时共享状态定义，描述每一步流转要携带的数据
|   |   |   `-- workflow.py                   # Agent 主工作流，负责加载记忆、路由意图、检索知识、查订单、风控和持久化
|   |   |
|   |   |-- models/
|   |   |   |-- __init__.py                   # models 包标记文件
|   |   |   `-- entities.py                   # 数据库 ORM 模型定义，如用户、商品、订单、聊天消息、状态快照、工单等
|   |   |
|   |   |-- repositories/
|   |   |   |-- __init__.py                   # repositories 包标记文件
|   |   |   `-- store.py                      # 数据访问层，封装常用数据库查询和写入逻辑
|   |   |
|   |   |-- schemas/
|   |   |   |-- __init__.py                   # schemas 包标记文件
|   |   |   |-- auth.py                       # 登录注册相关请求与响应模型
|   |   |   `-- chat.py                       # 聊天、会话、工单接口的数据结构定义
|   |   |
|   |   `-- services/
|   |       |-- __init__.py                   # services 包标记文件
|   |       |-- auth.py                       # 密码哈希、JWT 签发与登录 Cookie 管理
|   |       |-- bootstrap.py                  # 启动期准备逻辑，比如初始化数据库、写入种子数据、构建向量索引
|   |       |-- heuristics.py                 # 规则兜底模块，负责做轻量意图猜测、订单号提取和风险词识别
|   |       |-- llm.py                        # 大模型与向量模型调用封装，支持真实百炼接口和 mock 模式
|   |       |-- memory.py                     # 会话记忆管理，协调 Redis 短期记忆和 MySQL 长期记忆
|   |       |-- milvus_store.py               # Milvus 向量库操作封装，负责建集合、写入文档和相似度检索
|   |       `-- policy.py                     # 售后政策判断逻辑，根据订单状态和时间规则给出是否支持退换货
|   |
|   `-- tests/
|       |-- test_heuristics.py                # 规则层测试，验证订单号提取、意图判断等基础逻辑
|       `-- test_policy.py                    # 售后政策测试，验证退换货判断是否符合预期
|
`-- frontend/
    |-- Dockerfile                            # 前端镜像构建文件
    |-- next-env.d.ts                         # Next.js 自动生成的 TypeScript 环境声明文件
    |-- next.config.ts                        # Next.js 运行配置
    |-- package.json                          # 前端依赖与脚本声明
    |-- package-lock.json                     # 前端依赖锁文件
    |-- tsconfig.json                         # TypeScript 编译配置
    |
    |-- app/
    |   |-- globals.css                       # 全局样式和设计变量
    |   |-- layout.tsx                        # 应用根布局，负责统一页面壳子和基础元信息
    |   |-- auth/
    |   |   `-- page.tsx                      # 登录 / 注册页面入口
    |   |-- page.tsx                          # 首页入口，默认展示聊天工作台
    |   |
    |   |-- debug/
    |   |   `-- page.tsx                      # 调试页入口，用来查看会话状态和手动重建记忆
    |   |
    |   `-- tickets/
    |       `-- page.tsx                      # 工单页入口，用来查看转人工记录
    |
    |-- components/
    |   |-- app-shell.tsx                     # 登录后的主应用外壳，提供侧边栏、新建对话、导航和用户区
    |   |-- auth-provider.tsx                 # 全局登录态管理，负责恢复当前用户和提供登录/退出能力
    |   |-- auth-screen.tsx                   # 登录 / 注册界面组件
    |   |-- chat-workspace.tsx                # GPT 风格聊天主界面，负责会话加载、发消息和展示引用
    |   |-- debug-console.tsx                 # 调试界面组件，展示会话详情、状态快照和记忆重建结果
    |   |-- shell-boundary.tsx                # 根据当前路由决定是否套主应用壳子
    |   |-- tickets-board.tsx                 # 当前用户的工单列表组件
    |   `-- workspace-provider.tsx            # 会话列表管理，负责拉取历史会话和创建新对话
    |
    `-- lib/
        `-- api.ts                            # 前端统一 API 请求封装和共享类型定义
```

## 启动项目

1. 复制环境变量模板

```bash
cp .env.example .env
```

2. 如果你要接真实百炼模型，补充这些配置

- `DASHSCOPE_API_KEY=你的百炼密钥`
- `USE_MOCK_LLM=false`

如果你只是先本地演示，可以保留：

- `USE_MOCK_LLM=true`

3. 启动所有服务

```bash
docker compose up --build
```

4. 打开页面

- 前端：`http://localhost:3000`
- 后端 Swagger：`http://localhost:8000/docs`
- 登录页：`http://localhost:3000/auth`

## 主要接口

### `POST /api/auth/register`

注册新用户，并自动写入登录 Cookie。

### `POST /api/auth/login`

用户登录，并自动写入登录 Cookie。

### `POST /api/auth/logout`

清除登录 Cookie。

### `GET /api/auth/me`

获取当前登录用户信息。

### `GET /api/sessions`

获取当前登录用户的历史会话列表。

### `POST /api/sessions`

创建一个空会话，供“新对话”按钮直接使用。

### `POST /api/chat`

发起一轮客服对话，返回：

- `session_id`
- `reply`
- `intent`
- `citations`
- `used_tools`
- `memory_source`
- `needs_handoff`

### `GET /api/sessions/{session_id}`

查看完整会话详情，包括：

- 用户和助手消息
- 每一轮保存的状态快照
- 当前会话意图

### `GET /api/tickets`

查看当前登录用户的人工工单。

### `POST /api/knowledge/reindex`

重建 Milvus 知识库索引。

### `POST /api/memory/rebuild/{session_id}`

在 Redis 丢失或清空后，从 MySQL 历史快照恢复短期记忆。

## 建议演示脚本

0. 先登录演示账号：`demo@shopmate.local / demo123456`
1. 商品咨询：`AeroFit 智能运动耳机适合跑步吗？`
   登录后点击“新建对话”，观察 session 会自动创建，首条消息会自动成为会话标题。
2. 物流查询：`帮我查一下 ORD-10002 现在到哪了`
3. 退货判断：`订单 ORD-10003 还能退吗？`
4. 投诉转人工：`这个订单太离谱了，我要投诉并申请补偿`

## 如何快速理解这个项目

你可以按下面这条主线来理解：

1. 这是一个电商客服 Agent 项目，不是简单聊天机器人
2. 后端用 LangGraph 把客服流程拆成多个节点，比如记忆加载、意图路由、知识检索、订单查询、售后判断和人工转单
3. 商品和政策问题走 Milvus 检索，订单和退款问题走 MySQL 工具查询
4. Redis 保存短期记忆，MySQL 保存长期历史和状态快照
5. 风险场景不会让模型直接承诺补偿，而是自动转人工

如果你想继续深挖，可以重点看这些问题：

- 为什么要用 LangGraph 而不是直接 prompt
- 为什么订单和退款不能只交给模型判断
- 为什么记忆要拆成 Redis 和 MySQL 两层
- 为什么知识库要放在 Milvus 而不是直接塞进 prompt
