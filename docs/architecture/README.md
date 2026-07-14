# Architecture Reference

> 给需要理解系统边界、接口和部署取舍的人。这里回答“系统如何组成、请求如何走、为什么这样分工”，不承担日常启动步骤。

## 阅读顺序

1. [ARCHITECTURE](ARCHITECTURE.md)：先建立节点、服务和数据流全貌。
2. [API](API.md)：再看模型别名、请求格式、认证和错误码。
3. [NETWORK](NETWORK.md)：理解反向隧道、端口和安全组。
4. [MODEL_RESEARCH](MODEL_RESEARCH.md)：最后看模型与硬件的取舍证据。

## 完成标准

- 能画出客户端、LiteLLM、SSH 隧道和本地节点之间的请求方向。
- 能解释云服务器只做轻量控制面。
- 能知道某个模型别名和接口规则应去哪里查。

## 下一步

- 要实际部署或恢复服务：进入 [operations](../operations/README.md)。
- 要验证模型或客户端行为：进入 [quality](../quality/README.md)。
