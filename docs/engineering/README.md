# Engineering Design

> 给阅读或修改 RAG、Router、提示词规则和 review 决策的人。先读设计说明，再进入 services 代码，避免只凭文件名修改。

## 阅读顺序

1. [RAG Learning Notes](RAG_LEARNING_NOTES.md)：语料、切块、embedding、检索、引用和当前边界。
2. [Agent Router Learning Notes](AGENT_ROUTER_LEARNING_NOTES.md)：文本、图片、项目知识三条路由分支。
3. [Agent Operating Rules](AGENT_OPERATING_RULES.md)：提示词、外部参考材料和工程约束。
4. [Code Review Triage](CODE_REVIEW_TRIAGE.md)：为什么某些建议已采纳、延后或拒绝。
5. 再读 services/rag 和 services/agent 的源码。

## 完成标准

- 能区分 RAG 检索、最终生成和 Agent Router 编排。
- 能说明 Router 当前不是完整 Agent Runtime。
- 改动后知道要补哪些测试、文档和质量验证。

## 下一步

- 需要评测或客户端回归：进入 [quality](../quality/README.md)。
- 需要查看未来实现顺序：进入 [project](../project/README.md)。
