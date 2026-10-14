# BeninSpeechLab - Configure and verify PKCE S256 for a local Keycloak client.
# Run from PowerShell on the Docker Desktop host. No passwords are stored in this script.
[CmdletBinding()]
param(
    [string]$Container = "beninspeechlab-keycloak",
    [string]$Realm = "beninspeechlab",
    [string]$ClientId = "beninspeechlab-web",
    [string]$Server = "http://127.0.0.1:8080"
)
$ErrorActionPreference = "Stop"
$cli = "/opt/keycloak/bin/kcadm.sh"
$tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("bsl-pkce-" + [guid]::NewGuid().ToString("N") + ".json")
$remote = "/tmp/bsl-pkce-" + [guid]::NewGuid().ToString("N") + ".json"
function Invoke-Kc([string[]]$ArgsList) {
    # Windows PowerShell 5.1 turns native stderr into a terminating NativeCommandError\n    # under Stop. Capture it as output and check the native exit code ourselves.\n    $previousPreference = $ErrorActionPreference\n    $ErrorActionPreference = "Continue"\n    try {\n        $out = & docker exec $Container $cli @ArgsList 2>&1\n        $code = $LASTEXITCODE\n    } finally {\n        $ErrorActionPreference = $previousPreference\n    }\n    if ($code -ne 0) { throw "Keycloak CLI exited $code: $($out | Out-String)" }\n    return ($out | Out-String)
}
try {
    & docker inspect $Container --format '{{.State.Running}}' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Container '$Container' not found" }
    Write-Host "Checking Keycloak admin session..." -ForegroundColor Cyan
    try {
        $raw = Invoke-Kc @("get", "clients", "-r", $Realm, "-q", "clientId=$ClientId")
    } catch {
        Write-Host "Admin login required. Enter your Keycloak MASTER administrator password at the prompt." -ForegroundColor Yellow
        & docker exec -it $Container $cli config credentials --server $Server --realm master --user admin
        if ($LASTEXITCODE -ne 0) { throw "Keycloak admin login failed" }
        $raw = Invoke-Kc @("get", "clients", "-r", $Realm, "-q", "clientId=$ClientId")
    }
    $matches = @($raw | ConvertFrom-Json)
    if ($matches.Count -ne 1 -or $matches[0].clientId -ne $ClientId) {
        throw "Expected exactly one client '$ClientId'; got $($matches.Count). No change made."
    }
    $id = $matches[0].id
    Write-Host "Client: $ClientId ($id)" -ForegroundColor Cyan
    # Read the full current representation and modify only its attributes map.
    $full = Invoke-Kc @("get", "clients/$id", "-r", $Realm) | ConvertFrom-Json
    if ($null -eq $full.attributes) {
        $full | Add-Member -MemberType NoteProperty -Name attributes -Value ([pscustomobject]@{}) -Force
    }
    $full.attributes | Add-Member -MemberType NoteProperty -Name "pkce.code.challenge.method" -Value "S256" -Force
    # Write UTF-8 WITHOUT BOM; Windows PowerShell 5.1 defaults can add a BOM.
    [System.IO.File]::WriteAllText($tmp, ($full | ConvertTo-Json -Depth 100 -Compress), (New-Object System.Text.UTF8Encoding($false)))
    & docker cp $tmp "${Container}:$remote" | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "docker cp failed" }
    Write-Host "Applying client configuration..." -ForegroundColor Cyan
    Invoke-Kc @("update", "clients/$id", "-r", $Realm, "-f", $remote) | Out-Null
    # Read the complete representation, not just --fields, to verify persistence.
    $verify = Invoke-Kc @("get", "clients/$id", "-r", $Realm) | ConvertFrom-Json
    $method = $verify.attributes.'pkce.code.challenge.method'
    if ($method -ne "S256") {
        Write-Warning "Keycloak did not persist PKCE. Actual value: '$method'."
        Write-Warning "No claim of success. Check Keycloak logs and client policies before continuing."
        exit 2
    }
    Write-Host "SUCCESS: PKCE S256 is enforced for '$ClientId' in realm '$Realm'." -ForegroundColor Green
} finally {
    Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
    & docker exec $Container rm -f $remote 2>$null | Out-Null
}
