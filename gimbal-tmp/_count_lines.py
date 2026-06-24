"""统计 GIMBAL 项目的代码行数"""
import os
from pathlib import Path


def count_lines(base, pattern="*.py"):
    total_lines = 0
    total_files = 0
    for p in Path(base).rglob(pattern):
        if "__pycache__" in str(p):
            continue
        with open(p, "r", encoding="utf-8", errors="ignore") as f:
            lines = sum(1 for _ in f)
            total_lines += lines
            total_files += 1
    return total_lines, total_files


# 源代码
src_lines, src_files = count_lines("src")
print(f"=== src/gimbal/ (核心框架) ===")
print(f"  代码行: {src_lines:>6}  |  文件: {src_files}")
print()

# 测试
test_lines, test_files = count_lines("tests")
print(f"=== tests/ ===")
print(f"  代码行: {test_lines:>6}  |  文件: {test_files}")
print()

# 插件
plug_lines, plug_files = count_lines("plugins")
print(f"=== plugins/ ===")
print(f"  代码行: {plug_lines:>6}  |  文件: {plug_files}")
print()

# 子模块细分
print("=== src/gimbal/ 子模块 ===")
sub_stats = []
for sub in sorted(Path("src/gimbal").iterdir()):
    if sub.is_dir() and sub.name != "__pycache__":
        lines, files = count_lines(sub)
        sub_stats.append((sub.name, lines, files))
        print(f"  {sub.name:<20} {lines:>6} 行  ({files:>2} 个文件)")
print()

# 测试子目录
print("=== tests/ 子目录 ===")
for sub in sorted(Path("tests").iterdir()):
    if sub.is_dir():
        lines, files = count_lines(sub)
        print(f"  {sub.name:<20} {lines:>6} 行  ({files:>2} 个文件)")
print()

# 总计
total_py = src_lines + test_lines + plug_lines
total_files = src_files + test_files + plug_files
print(f"=== 总计 Python ===")
print(f"  代码行: {total_py}  |  文件: {total_files}")
print(f"  测试/源码比: 1 : {src_lines / test_lines:.2f}")
print()

# TOP 10 最大文件
print("=== TOP 10 最大源文件 ===")
file_list = []
for p in Path("src/gimbal").rglob("*.py"):
    if "__pycache__" in str(p):
        continue
    with open(p, "r", encoding="utf-8", errors="ignore") as f:
        lines = sum(1 for _ in f)
        file_list.append((lines, str(p)))
file_list.sort(reverse=True)
for lines, path in file_list[:10]:
    relpath = path.replace("\\", "/")
    print(f"  {lines:>5} 行  {relpath}")