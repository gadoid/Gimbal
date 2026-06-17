# Gimbal 测试框架文档

Gimbal 是一个 **API 测试框架** (Python 3.11+)，支持复杂的 HTTP API 测试场景编排。

## 项目概述

Gimbal 提供了完整的 API 测试解决方案，包括：
- 场景编排与执行
- 多阶段策略执行（Extract/Assign/Assertion）
- 状态机驱动的步骤执行
- 灵活的认证管理
- 模板变量解析
- 完善的日志和可观测性
- 插件扩展机制

## 核心架构

```
CLI
  │
  ▼
bootstrap() → Configuration
  │
  ▼
Engine
  │
  ├── Scenario → ScenarioRunner → StepRunner → StepStateMachine
  │                                           │
  │                                           └── 状态机驱动执行
  │
  └── Suite → 遍历 Scenario
```

## 模块文档

### 核心模块

| 模块 | 说明 |
|------|------|
| [core](modules/core.md) | 核心执行引擎，bootstrap、Engine、ScenarioRunner |
| [statemachine](modules/statemachine.md) | 状态机，驱动 Step 执行流程 |
| [strategy](modules/strategy.md) | 策略系统，Extract/Assign/Assertion |
| [schema](modules/schema.md) | Pydantic 数据模型 |

### 执行上下文

| 模块 | 说明 |
|------|------|
| [context](modules/context.md) | 层级执行上下文 (Framework→Suite→Scenario→Step) |
| [config](modules/config.md) | 配置管理，多来源配置合并 |
| [generator](modules/generator.md) | 变量生成器（7 个内置 kind：uuid / random_str / random_int / random_decimal / timestamp / now / seq） |

### 支持模块

| 模块 | 说明 |
|------|------|
| [preprocessor](modules/preprocessor.md) | 预处理：引用物化、认证、模板展开 |
| [auth](modules/auth.md) | 认证管理 |
| [cli](modules/cli.md) | 命令行接口 |
| [compiler](modules/compiler.md) | 场景文件编译 |
| [events](modules/events.md) | 事件系统 |
| [reporter](modules/reporter.md) | 测试报告 |
| [repository](modules/repository.md) | 资产仓库 |
| [resource](modules/resource.md) | 资源管理 |
| [scheduler](modules/scheduler.md) | 测试调度 |
| [suite](modules/suite.md) | 套件管理 |
| [plugins](modules/plugins.md) | 插件系统 |
| [observability](modules/observability.md) | 可观测性（日志、追踪、指标） |
| [utils](modules/utils.md) | 工具函数（JSONPath） |
| [ai](modules/ai.md) | AI 辅助功能 |

## 状态机流程

```
PENDING
  └─→ BEFORE_REQUEST   (Assign 等前置策略)
        ├─→ CALLING        (HTTP 请求)
        └─→ TEARDOWN       (hard-fail)
    CALLING
          ├─→ AFTER_REQUEST  (请求成功)
          └─→ TEARDOWN       (请求失败)
    AFTER_REQUEST
          ├─→ VERIFYING      (Extract 等后置策略)
          └─→ TEARDOWN
    VERIFYING
          ├─→ PASSED
          ├─→ FAILED
          └─→ TEARDOWN       (有 teardown 策略)
    TEARDOWN
          ├─→ PASSED
          └─→ FAILED
```

## 策略类型

| 策略 | 阶段 | 说明 |
|------|------|------|
| Assign | BEFORE_REQUEST | 准备入参、变量赋值 |
| Call | CALLING | HTTP 调用 |
| Extract | AFTER_REQUEST | 提取响应字段 |
| Assertion | VERIFYING | 断言验证 |
| Teardown | TEARDOWN | 清理、资源释放 |

## 配置优先级

```
CLI 参数 (最高)
    ↓
环境变量 (GIMBAL_*)
    ↓
mode 配置文件 (./mode/{mode}.yml)
    ↓
env 配置文件 (./env/gimbal_{env}.yml)
    ↓
gimbal.yaml
    ↓
内置默认值 (最低)
```

## 快速开始

### 1. 安装

```bash
pip install gimbal
```

### 2. 创建场景文件

```yaml
# login.yaml
kind: scenario
scenarioId: sc-login-001
meta:
  name: 用户登录测试
  description: 测试用户登录流程
  module: user
  priority: 1
  author: test
  owner: test
  tags: [smoke, login]
  version: "1.0"
config:
  services:
    user-service: http://localhost:8080
  users:
    admin:
      url: http://localhost:8080/auth/login
      username: admin
      password: admin123
steps:
  - api:
      service: user-service
      method: POST
      path: /api/login
    request:
      body:
        username: "${auth.admin.username}"
        password: "${auth.admin.password}"
    strategy:
      - kind: extract
        source: response_body
        expression: "$.token"
        target: access_token
      - kind: assertion
        target: response_status
        operator: eq
        expected: 200
```

### 3. 执行测试

```bash
gimbal run scenario login.yaml
```

## 设计原则

1. **Configuration 不可变**: BootstrapConfig 创建后不可修改
2. **数据单向流动**: 低层 → 高层，通过 `promote_from()` 受控提升
3. **Seal 机制**: Context 执行完毕后封印，防止意外修改
4. **状态机驱动**: 步骤执行由状态机控制，流程清晰
5. **策略可扩展**: 通过注册机制支持自定义策略
6. **Frozen 产出**: bootstrap 产出的 Configuration 是 frozen 的