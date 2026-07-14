# LabAgent 文档门户

> 从这里选择你的角色，而不是一次读完所有文档。每个目录都有自己的 README，进入后只看与当前任务有关的资料。

## 先选一条路径

| 你现在要做什么 | 入口 | 读到什么程度算够 |
|----------------|------|------------------|
| 第一次认识项目 | [getting-started](getting-started/README.md) | 能画出客户端、云网关和本地 GPU 的链路 |
| 启动、巡检或排障 | [operations](operations/README.md) | 能按层定位模型、隧道、网关和服务故障 |
| 理解接口、网络或模型分工 | [architecture](architecture/README.md) | 能说明请求如何路由，以及为什么这样部署 |
| 阅读或修改 RAG / Router | [engineering](engineering/README.md) | 能找到代码入口、设计边界和验证方式 |
| 验证模型、客户端或回归结果 | [quality](quality/README.md) | 能选择合适的 benchmark 或兼容性矩阵 |
| 了解进度、规划或面试表达 | [project](project/README.md) | 能区分已完成能力、限制和下一步 |
| 追溯过去的决策 | [history](history/README.md) | 能找到变更时间和原始排障上下文 |

## 推荐阅读层级

1. 第一层：只读 getting-started。零基础读者先建立整体心智模型。
2. 第二层：按当前职责进入一个分类目录，不跨目录跳读。
3. 第三层：需要改代码、排障或写评审材料时，才打开 engineering、quality、project 和 history 的深度文档。

## 目录边界

    docs/
    ├── getting-started/   新人学习与基础概念
    ├── architecture/      架构、API、网络、模型选择
    ├── operations/        部署、运行和故障恢复
    ├── engineering/       RAG、Router 与工程规则
    ├── quality/           Benchmark 与客户端兼容性
    ├── project/           进度、规划、评审和学习路线
    └── history/           变更与历史过程

## 当前事实在哪里

| 需要确认的事实 | 唯一入口 |
|----------------|----------|
| 今天服务是否应该启动、端口和重启顺序 | [HANDOFF](../HANDOFF.md) 和 [operations](operations/README.md) |
| 架构、模型别名、API 与网络 | [architecture](architecture/README.md) |
| RAG / Router 的实现和边界 | [engineering](engineering/README.md) |
| 模型质量和客户端支持范围 | [quality](quality/README.md) |
| 项目当前阶段、求职和后续计划 | [project](project/README.md) |
| 历史事件 | [history](history/README.md)，不能代替当前事实 |

## 维护规则

- 新文档先放入已有分类；只有出现新的长期职责时才创建目录。
- 分类 README 只维护阅读顺序、文档职责和完成标准；事实仍放在专题文档。
- 移动文档时同步更新链接、RAG discovery、测试和本地 RAG index。详细规则见 [Documentation Sync](project/DOCUMENTATION_SYNC.md)。

本机忽略的外部 review、外部 AI 建议和原始系统提示词不属于正式文档体系，不进入 Git 或默认 RAG discovery。
