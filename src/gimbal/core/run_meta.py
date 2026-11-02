"""Run 级元数据收集（CI/CD 上下文 / git 信息 / 触发人）。

由 ``bootstrap()`` 调用一次、挂到 ``Configuration.run_meta``,再由
``Engine.run`` 在 reporter 订阅完成（``reporter_runtime.begin_all``）之后
包成 ``RunMetaEvent`` 发布 —— 此前 CLI 在 ``Engine.run`` 之前发布,总线无
回放,HTML/JSON reporter 永远收不到（全量评估 2026-11-02 #4）。

原在 ``gimbal.cli.common._collect_run_meta``;收集面是纯环境变量读取,
与 CLI 无关,挪到 core 让 server / 平台入口同样带上。
"""
from __future__ import annotations

import os
from typing import Any


def collect_run_meta() -> dict[str, Any]:
    """收集本次运行的元数据（CI/CD 上下文 / git 信息 / 触发人 / 业务扩展）。

    数据来源：
      - 环境变量：CI 平台约定的标准变量（GitHub Actions / GitLab CI / Jenkins / 通用）
      - 用户可在 ~/.gimbal/env 或 gimbal.toml 的 [run_meta] 段补充自定义键值

    兼容设计：
      - 所有字段都有 default；任何环境变量缺失都不会抛错
      - 字段名为人类可读，与 HTML 报告头部 pill 一一对应
    """
    return {
        # CI/CD 上下文
        "ci":              bool(os.environ.get("CI")),
        "ci_provider":     os.environ.get("CI_PROVIDER", ""),     # 手动指定
        "build_url":       os.environ.get("BUILD_URL", "") or os.environ.get("CI_BUILD_URL", "") or os.environ.get("GITHUB_SERVER_URL", ""),
        "build_number":    os.environ.get("BUILD_NUMBER", "") or os.environ.get("GITHUB_RUN_NUMBER", "") or os.environ.get("CI_PIPELINE_ID", ""),
        "build_id":        os.environ.get("BUILD_ID", "") or os.environ.get("GITHUB_RUN_ID", ""),
        # Git 上下文（短名：与 HTML 报告头部 pill / JsonReporter dump 对齐）
        "branch":          os.environ.get("GIT_BRANCH", "") or os.environ.get("GITHUB_REF_NAME", "") or os.environ.get("CI_COMMIT_REF_NAME", ""),
        "commit":          (os.environ.get("GIT_COMMIT", "") or os.environ.get("GITHUB_SHA", "") or os.environ.get("CI_COMMIT_SHA", ""))[:12],
        "commit_msg":      (os.environ.get("GIT_COMMIT_MESSAGE", "") or os.environ.get("CI_COMMIT_MESSAGE", ""))[:120],
        # 触发人
        "triggered_by":    os.environ.get("GIT_AUTHOR", "") or os.environ.get("GITHUB_ACTOR", "") or os.environ.get("CI_COMMIT_AUTHOR", "") or os.environ.get("USER", "") or os.environ.get("USERNAME", ""),
    }
