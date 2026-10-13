# restart-services.ps1 — 三服务脱离会话外壳启动(2026-09-28)
# 背景:run_in_background 的 bash 外壳被回收时会带走整个进程树(启动
# 正常、探针绿、随后无痕消失,外壳报 exit 127)。Start-Process 让进程
# 挂在自己的树里,与会话 shell 解耦;输出重定向到各目录日志文件。
$ErrorActionPreference = 'Continue'

# plate 构件根(版本模型 3.6/B2 唯一来源):plate/artifacts 分支的检出,
# 发版/按修订读取/冷化都从这里取;子进程继承本变量(2026-10-12 W14)。
$env:PLATE_ARTIFACTS_PATH = 'D:\Gimbal\plate-artifacts'

Start-Process -FilePath 'python' -ArgumentList 'run_plate.py' `
  -WorkingDirectory 'D:\Gimbal\Gimbal\src\gimbal-plate' -WindowStyle Hidden `
  -RedirectStandardOutput 'D:\Gimbal\Gimbal\src\gimbal-plate\plate-out.log' `
  -RedirectStandardError  'D:\Gimbal\Gimbal\src\gimbal-plate\plate-err.log'

Start-Process -FilePath 'python' `
  -ArgumentList '-m','uvicorn','app.main:app','--host','0.0.0.0','--port','8000' `
  -WorkingDirectory 'D:\Gimbal\Gimbal\src\gimbal-platform\backend' -WindowStyle Hidden `
  -RedirectStandardOutput 'D:\Gimbal\Gimbal\src\gimbal-platform\backend\interaction-rollout.log' `
  -RedirectStandardError  'D:\Gimbal\Gimbal\src\gimbal-platform\backend\interaction-rollout.err.log'

Start-Process -FilePath 'cmd' -ArgumentList '/c','npm','run','dev' `
  -WorkingDirectory 'D:\Gimbal\Gimbal\src\gimbal-platform\frontend' -WindowStyle Hidden `
  -RedirectStandardOutput 'D:\Gimbal\Gimbal\src\gimbal-platform\frontend\vite-out.log' `
  -RedirectStandardError  'D:\Gimbal\Gimbal\src\gimbal-platform\frontend\vite-err.log'
