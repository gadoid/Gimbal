"""compiler/errors.py — 编译错误类型（独立模块避免 pipeline/modes 循环）。"""


class CompileError(Exception):
    """编译失败（用户输入问题；CLI 层转 exit code 2）。"""
