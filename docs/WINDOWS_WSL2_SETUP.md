# Windows WSL2 / CUDA 配置指南

> 适用对象：5090 主机、新设备（RTX 4090D 24GB + RTX 4060 Ti 16GB）。  
> 8060S 当前无法使用，暂不纳入近期 WSL2 / CUDA 配置计划。  
> 目标：为 vLLM / SGLang / llama.cpp / RAG / Agent Runtime 准备 Linux 开发环境。

## 什么时候需要 WSL2

LM Studio 可以继续在 Windows 原生环境里跑，用来快速验证模型和 OpenAI-compatible API。

需要 WSL2 的场景：

- 部署 vLLM / SGLang 等更偏 Linux 的推理服务。
- 跑 CUDA / PyTorch 生态工具。
- 容器化 RAG、Agent、评测服务。
- 后续做 LoRA / QLoRA 微调实验。

## 安装前检查

1. Windows 11 推荐。
2. BIOS 里开启虚拟化（Intel VT-x / AMD SVM）。
3. 安装最新 NVIDIA Windows 驱动。CUDA on WSL 使用 Windows 侧 NVIDIA 驱动，不要在 WSL 里安装 Linux GPU 驱动。
4. PowerShell 用管理员权限打开。

## 安装 WSL2

管理员 PowerShell：

```powershell
wsl --install -d Ubuntu-24.04
```

如果系统提示重启，重启后再次打开 Ubuntu，完成用户名和密码初始化。

检查状态：

```powershell
wsl -l -v
```

确认 Ubuntu 的 `VERSION` 是 `2`。如果不是：

```powershell
wsl --set-version Ubuntu-24.04 2
wsl --set-default-version 2
```

更新 WSL：

```powershell
wsl --update
wsl --shutdown
```

重新打开 Ubuntu。

## Ubuntu 基础环境

在 WSL Ubuntu 中执行：

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y git curl wget build-essential python3 python3-venv python3-pip
```

建议创建项目工作目录：

```bash
mkdir -p ~/labagent
cd ~/labagent
```

## 验证 GPU 可见

在 WSL Ubuntu 中：

```bash
nvidia-smi
```

新设备上预期能同时看到 RTX 4090D 和 RTX 4060 Ti。

如果 `nvidia-smi` 不存在或报错：

1. 先确认 Windows 任务管理器能看到 NVIDIA GPU。
2. 更新 Windows NVIDIA 驱动。
3. 执行 `wsl --shutdown` 后重开 Ubuntu。
4. 不要在 WSL 里安装 Linux 显卡驱动。

## 安装 Python / PyTorch CUDA 验证

创建虚拟环境：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
```

按 PyTorch 官网当前命令安装 CUDA 版 PyTorch。安装后验证：

```bash
python - <<'PY'
import torch
print("cuda available:", torch.cuda.is_available())
print("device count:", torch.cuda.device_count())
for i in range(torch.cuda.device_count()):
    print(i, torch.cuda.get_device_name(i))
PY
```

## 多 GPU 注意事项

新设备是 RTX 4090D 24GB + RTX 4060 Ti 16GB 混插。建议：

1. 不要默认让大模型自动跨两张不同显存/性能的卡，先单卡跑稳定。
2. 4090D 作为主推理卡，4060 Ti 做 embedding、rerank、轻量模型或评测任务。
3. 用 `CUDA_VISIBLE_DEVICES` 固定进程使用哪张卡：

```bash
CUDA_VISIBLE_DEVICES=0 python your_script.py
CUDA_VISIBLE_DEVICES=1 python your_script.py
```

实际编号以 `nvidia-smi` 显示为准。

## 推荐下一步

1. 先在新设备安装 WSL2 并跑通 `nvidia-smi`。
2. 安装 Python / PyTorch 并确认能识别 4090D 和 4060 Ti。
3. 先跑轻量 benchmark，不急着装 vLLM。
4. 再决定新设备上用 LM Studio、llama.cpp、SGLang 还是 vLLM。

## 参考来源

- Microsoft WSL 安装文档：https://learn.microsoft.com/en-us/windows/wsl/install
- Microsoft CUDA on WSL 指南：https://learn.microsoft.com/en-us/windows/ai/directml/gpu-cuda-in-wsl
- NVIDIA CUDA on WSL User Guide：https://docs.nvidia.com/cuda/wsl-user-guide/index.html
