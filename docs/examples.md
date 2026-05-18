# Examples Index

本目录包含 Gimbal 框架的运行示例。

## 目录结构

```
examples/
├── asset_library/          # 资产库示例
├── hello/                  # Hello World 示例
├── login_and_query/        # 登录与查询示例
└── suites/                 # Suite 示例
```

## 快速开始

### Hello World

最简单的 Scenario 示例：

```bash
gimbal run launch examples/hello/scenario.yaml
```

### 登录与查询

展示多个 Step 协同工作的完整示例：

```bash
gimbal run launch examples/login_and_query/scenario.yaml
```

### 执行 Suite

执行包含多个 Scenario 的 Suite：

```bash
gimbal run suite examples/suites/my-suite.yaml
```

## 示例说明

### examples/hello/

最简单的示例，展示：
- Scenario 基本结构
- 单个 Step 定义
- HTTP GET 请求
- 基本断言

### examples/login_and_query/

展示完整的工作流：
- 多个 Step 顺序执行
- 变量提取 (Extract) 和传递
- 认证信息注入 (Assign)
- 多步骤验证

### examples/suites/

展示 Suite 层级的使用：
- 多个 Scenario 组合
- 共享配置
- 执行顺序控制

### examples/asset_library/

展示资产库的使用：
- 资产定义与注册
- 资产引用
- 资产解析

## 如何运行示例
