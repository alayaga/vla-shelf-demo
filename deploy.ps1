# 将静态站点部署到远程 Nginx（本文件不含任何密码或默认主机）。
# 用法：
#   1. 复制 deploy.env.example 为 deploy.env（已被 gitignore）并填写；或
#   2. 手动设置环境变量后执行 .\deploy.ps1
#
# 必需环境变量：
#   ALIYUN_HOST
#   ALIYUN_SSH_PASSWORD
# 可选：
#   ALIYUN_USER（默认 root）

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

$deployEnv = Join-Path $here "deploy.env"
if (Test-Path $deployEnv) {
    Get-Content $deployEnv | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#")) { return }
        $parts = $line.Split("=", 2)
        if ($parts.Count -eq 2) {
            $name = $parts[0].Trim()
            $value = $parts[1].Trim()
            if ($name) {
                Set-Item -Path "Env:$name" -Value $value
            }
        }
    }
}

if (-not $env:ALIYUN_HOST) {
    Write-Error "请设置 ALIYUN_HOST（可复制 deploy.env.example 为 deploy.env 后填写）。"
}
if (-not $env:ALIYUN_SSH_PASSWORD) {
    Write-Error "请设置 ALIYUN_SSH_PASSWORD（可复制 deploy.env.example 为 deploy.env 后填写）。"
}

$py = Join-Path $here "deploy_once.py"
if (-not (Test-Path $py)) {
    Write-Error "Missing deploy_once.py"
}

python $py
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host "部署完成。请在浏览器打开你的站点地址并 Ctrl+F5 强制刷新。"
