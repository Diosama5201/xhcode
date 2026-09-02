# XHCode
OVO欢迎光临！
XHCode 是一款命令行 AI 编程 Agent。基于 **ReAct** 智能体架构，借助 MCP 工具调用协议，Agent 可以自主完成代码生成、代码修改、BUG排查、文件读写、脚本执行等开发任务，通过配置即可切换不同大模型后端。

## ✨ Features
- 🤖 完整 ReAct Agent 执行循环，自主任务拆解、多轮工具迭代完成复杂编程需求
- 🔧 基于 MCP 协议实现工具调用，内置文件读写、脚本运行等开发工具
- ⚙️ 配置化驱动，支持兼容 OpenAI 接口的大模型（本项目LLM暂时用的Qwen‑Max）
- 🔐 自定义 YAML文件，配置文件直接读取系统环境变量，避免密钥硬编码泄露
- 📝 完整日志输出、参数校验、异常容错，处理工具调用失败、Agent死循环等边界场景

## 🛠 Tech Stack
- **Language**: Python
- **Agent**: ReAct Loop、MCP Tool Call Protocol
- **LLM Backend**: Qwen‑Max、DeepSeek，兼容 OpenAI API 规范
- **Config**: PyYAML（扩展自定义 `!env` 标签解析）
- **Others**: Async IO, API Request, Logging, Exception Handling

## 🚀 快速开始

### 1. 依赖安装
```bash
pip install -r requirements.txt
-----------------------------------
2 Configure LLM provider
providers:
  - name: qwen-max
    protocol: openai
    base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
    api_key: !env OPENAI_API_KEY
    model: qwen-max
    thinking: false
--------------------------------------
3 environment variable
Windows PowerShell
$env:OPENAI_API_KEY="sk-Your-API-Key-Here"
Linux / macOS
export OPENAI_API_KEY="sk-Your-API-Key-Here"
----------------------------------------------
4 Launch interactive agent terminal
python main.py

