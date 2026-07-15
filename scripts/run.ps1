param(
    [string]$LiteLLMConfig = "config\litellm_config.yaml",

    [switch]$SkipLiteLLM
)

$ErrorActionPreference = "Stop"

$ScriptsDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptsDir
Set-Location $ProjectRoot

function Import-DotEnv {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }

    foreach ($line in Get-Content -LiteralPath $Path) {
        $trimmed = $line.Trim()
        if ($trimmed.Length -eq 0 -or $trimmed.StartsWith("#")) {
            continue
        }

        if ($trimmed.StartsWith("export ")) {
            $trimmed = $trimmed.Substring(7).Trim()
        }

        $separator = $trimmed.IndexOf("=")
        if ($separator -le 0) {
            continue
        }

        $key = $trimmed.Substring(0, $separator).Trim()
        $value = $trimmed.Substring($separator + 1).Trim()

        if (
            ($value.StartsWith('"') -and $value.EndsWith('"')) -or
            ($value.StartsWith("'") -and $value.EndsWith("'"))
        ) {
            $value = $value.Substring(1, $value.Length - 2)
        }

        [Environment]::SetEnvironmentVariable($key, $value, "Process")
    }
}

function Resolve-ProjectPath {
    param([string]$Path)

    if ([System.IO.Path]::IsPathRooted($Path)) {
        return $Path
    }

    return Join-Path $ProjectRoot $Path
}

function Get-CommandPath {
    param(
        [string]$LocalPath,
        [string]$FallbackCommand
    )

    $fullLocalPath = Join-Path $ProjectRoot $LocalPath
    if (Test-Path -LiteralPath $fullLocalPath) {
        return $fullLocalPath
    }

    return $FallbackCommand
}

function New-ResolvedLiteLLMConfig {
    param(
        [string]$SourcePath,
        [string]$OutputPath
    )

    $content = Get-Content -LiteralPath $SourcePath -Raw
    $resolved = [regex]::Replace(
        $content,
        '"?os\.environ/([A-Za-z_][A-Za-z0-9_]*)"?',
        {
            param($match)

            $name = $match.Groups[1].Value
            $value = [Environment]::GetEnvironmentVariable($name, "Process")
            if (-not $value) {
                throw "Environment variable required by LiteLLM config is missing: $name"
            }

            $escaped = $value.Replace("\", "\\").Replace('"', '\"')
            return '"' + $escaped + '"'
        }
    )

    Set-Content -LiteralPath $OutputPath -Value $resolved -Encoding UTF8
}

function Test-TcpPort {
    param(
        [string]$HostName,
        [int]$Port
    )

    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $connect = $client.BeginConnect($HostName, $Port, $null, $null)
        if (-not $connect.AsyncWaitHandle.WaitOne(500)) {
            return $false
        }
        $client.EndConnect($connect)
        return $true
    }
    catch {
        return $false
    }
    finally {
        $client.Close()
    }
}

Import-DotEnv (Join-Path $ProjectRoot ".env")
Import-DotEnv (Join-Path $ProjectRoot "config\.env")

if (-not $env:LITELLM_PROXY_BASE_URL) {
    $env:LITELLM_PROXY_BASE_URL = "http://localhost:4000"
}

if (-not $env:LITELLM_PROXY_HOST) {
    $env:LITELLM_PROXY_HOST = "127.0.0.1"
}

if (-not $env:LITELLM_PROXY_API_KEY) {
    $env:LITELLM_PROXY_API_KEY = "sk-local-dev"
}

$env:PYTHONUTF8 = "1"

$pythonCommand = Get-CommandPath ".venv\Scripts\python.exe" "python"
$litellmCommand = Get-CommandPath ".venv\Scripts\litellm.exe" "litellm"
$litellmConfigPath = Resolve-ProjectPath $LiteLLMConfig

if (-not (Test-Path -LiteralPath $litellmConfigPath)) {
    throw "LiteLLM config not found: $litellmConfigPath"
}

New-Item -ItemType Directory -Force -Path (Join-Path $ProjectRoot "logs") | Out-Null
$resolvedLiteLLMConfigPath = Join-Path $ProjectRoot "logs\litellm_config.resolved.yaml"
New-ResolvedLiteLLMConfig $litellmConfigPath $resolvedLiteLLMConfigPath

$proxyUri = [Uri]$env:LITELLM_PROXY_BASE_URL
$proxyHost = if ($proxyUri.Host -eq "localhost") { "127.0.0.1" } else { $proxyUri.Host }
$proxyPort = $proxyUri.Port
if ($proxyPort -lt 0) {
    $proxyPort = 4000
}
if ($proxyUri.Host -eq "localhost") {
    $env:LITELLM_PROXY_BASE_URL = "{0}://127.0.0.1:{1}{2}" -f $proxyUri.Scheme, $proxyPort, $proxyUri.AbsolutePath.TrimEnd("/")
}

$startedLiteLLM = $null
$nullDevice = if ($IsWindows -or $env:OS -eq "Windows_NT") { "NUL" } else { "/dev/null" }

try {
    if (-not $SkipLiteLLM) {
        if (Test-TcpPort $proxyHost $proxyPort) {
        }
        else {
            $startedLiteLLM = Start-Process `
                -FilePath $litellmCommand `
                -ArgumentList @("--config", $resolvedLiteLLMConfigPath, "--host", $env:LITELLM_PROXY_HOST, "--port", $proxyPort) `
                -WorkingDirectory $ProjectRoot `
                -WindowStyle Hidden `
                -RedirectStandardOutput $nullDevice `
                -RedirectStandardError $nullDevice `
                -PassThru

            $ready = $false
            for ($i = 0; $i -lt 60; $i++) {
                if ($startedLiteLLM.HasExited) {
                    throw "LiteLLM exited before becoming ready."
                }

                if (Test-TcpPort $proxyHost $proxyPort) {
                    $ready = $true
                    break
                }

                Start-Sleep -Seconds 1
            }

            if (-not $ready) {
                throw "LiteLLM did not become reachable at $env:LITELLM_PROXY_BASE_URL within 60 seconds."
            }
        }
    }

    & $pythonCommand -m streamlit run src/main.py --logger.level=error
    $appExitCode = if ($LASTEXITCODE -ne $null) { $LASTEXITCODE } else { 0 }
    exit $appExitCode
}
finally {
    if ($startedLiteLLM -and -not $startedLiteLLM.HasExited) {
        Stop-Process -Id $startedLiteLLM.Id -Force
    }
    if (Test-Path -LiteralPath $resolvedLiteLLMConfigPath) {
        Remove-Item -LiteralPath $resolvedLiteLLMConfigPath -Force
    }
}
