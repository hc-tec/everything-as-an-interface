# 文档中心

欢迎来到 Everything As An Interface 文档中心！

## 📖 文档导航

### 🚀 快速开始

| 文档 | 描述 | 适用人群 |
|------|------|---------|
| [项目 README](../README.md) | 项目概述、快速开始、基本使用 | 所有用户 |
| [CLAUDE.md](../CLAUDE.md) | Claude Code 工作指南、开发规范 | 开发者 |

### 📚 插件使用文档

| 文档 | 描述 | 适用人群 |
|------|------|---------|
| **[插件 API 完整参考](./plugins_api_reference.md)** | 所有插件的详细参数、返回值、使用示例 | 插件使用者 |
| **[插件快速参考表](./plugins_quick_reference.md)** | 快速查找插件ID、方法名和关键参数 | 插件使用者 |
| [小红书详情插件 v3.0 迁移指南](./xiaohongshu_details_v3_migration.md) | 从 v2.0 升级到 v3.0 的完整指南 | 现有用户 |

### 🔧 开发者文档

| 文档 | 描述 | 适用人群 |
|------|------|---------|
| [开发者 SOP](./developer_sop.md) | 开发标准操作流程 | 开发者 |
| [CLAUDE.md](../CLAUDE.md) | 项目架构、设计模式、开发规范 | 开发者 |

### 📝 示例代码

| 目录 | 描述 |
|------|------|
| [examples/](../examples/) | 各种使用场景的示例代码 |
| [client_sdk/](../client_sdk/) | RPC 客户端 SDK |

## 🗂️ 按主题分类

### 插件使用

- **首次使用？** → 从 [项目 README](../README.md) 开始
- **查找插件参数？** → 查看 [插件快速参考表](./plugins_quick_reference.md)
- **需要详细说明？** → 阅读 [插件 API 完整参考](./plugins_api_reference.md)
- **升级插件？** → 参考对应的迁移指南（如 [小红书详情 v3.0](./xiaohongshu_details_v3_migration.md)）

### 开发与贡献

- **了解架构？** → 阅读 [CLAUDE.md](../CLAUDE.md) 的架构部分
- **开发新插件？** → 参考 [CLAUDE.md](../CLAUDE.md) 插件开发部分
- **代码规范？** → 查看 [CLAUDE.md](../CLAUDE.md) 代码风格指南
- **提交代码？** → 遵循 [开发者 SOP](./developer_sop.md)

### 问题排查

- **Cookie 问题？** → [插件 API 参考 - Cookie 管理](./plugins_api_reference.md#cookie-管理)
- **超时问题？** → [插件快速参考 - 性能优化](./plugins_quick_reference.md#性能优化速查)
- **错误处理？** → [插件 API 参考 - 错误处理](./plugins_api_reference.md#错误处理示例)
- **调试技巧？** → [插件快速参考 - 调试技巧](./plugins_quick_reference.md#调试技巧)

## 🎯 常见场景指引

### 场景 1: 我想使用小红书收藏夹功能

1. 查看 [插件快速参考 - 小红书](./plugins_quick_reference.md#小红书-xiaohongshu)
2. 参考 [插件 API 参考 - xiaohongshu_favorites_brief](./plugins_api_reference.md#xiaohongshu_favorites_brief)
3. 运行 [示例代码](../examples/)

### 场景 2: 我想获取笔记详情

1. 查看 [插件快速参考 - 场景3](./plugins_quick_reference.md#场景3批量获取笔记详情)
2. 参考 [插件 API 参考 - xiaohongshu_details](./plugins_api_reference.md#xiaohongshu_details)
3. 如果是从 v2.0 升级，查看 [迁移指南](./xiaohongshu_details_v3_migration.md)

### 场景 3: 我想开发新插件

1. 阅读 [CLAUDE.md - 插件开发](../CLAUDE.md#插件开发)
2. 查看现有插件代码作为参考 (`src/plugins/`)
3. 遵循 [开发者 SOP](./developer_sop.md)

### 场景 4: 遇到错误或问题

1. 查看 [插件 API 参考 - 常见问题](./plugins_api_reference.md#常见问题)
2. 检查 [插件快速参考 - 调试技巧](./plugins_quick_reference.md#调试技巧)
3. 查看日志文件 `logs/app.log`
4. 提交 Issue 到 GitHub

## 📊 文档速查表

| 我想... | 查看文档 |
|---------|----------|
| 快速开始使用 | [README.md](../README.md) |
| 查找插件参数 | [插件快速参考](./plugins_quick_reference.md) |
| 了解插件详细信息 | [插件 API 参考](./plugins_api_reference.md) |
| 开发新功能 | [CLAUDE.md](../CLAUDE.md) |
| 查看代码示例 | [examples/](../examples/) |
| 升级插件版本 | 对应的迁移指南 |
| 解决问题 | [常见问题](#问题排查) |

## 🔗 外部资源

- [Playwright 文档](https://playwright.dev/python/)
- [FastAPI 文档](https://fastapi.tiangolo.com/)
- [Pydantic 文档](https://docs.pydantic.dev/)

## 📮 反馈与贡献

- **发现文档问题？** 请提交 Issue
- **想要改进文档？** 欢迎提交 Pull Request
- **需要帮助？** 查看 [常见问题](./plugins_api_reference.md#常见问题) 或提交 Issue

## 📅 文档更新日志

- **2025-01-15**: 创建插件 API 完整参考文档
- **2025-01-15**: 创建插件快速参考表
- **2025-01-15**: 创建小红书详情插件 v3.0 迁移指南
- **2025-01-15**: 创建文档索引

---

💡 **提示**: 使用浏览器的搜索功能（Ctrl+F 或 Cmd+F）可以快速查找文档中的关键词。
