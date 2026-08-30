# One-time R2 migration hop: publish v1.14.0 updater assets to the legacy R2
# feed so <=1.13.0 installs (whose baked-in updater still points at R2) can
# reach 1.14.0 - the first build whose updater feeds from GitHub Releases.
# After old clients hop, the bucket/keys/domain can be retired.
#
# Usage:
#   $env:AWS_ACCESS_KEY_ID=...; $env:AWS_SECRET_ACCESS_KEY=...; pwsh scripts/sync_r2_one_last_time.ps1
param(
  [string]$Tag = "v1.14.0",
  [string]$Endpoint = "https://5bf0e92040869b5b56123207a122dc6d.r2.cloudflarestorage.com",
  [string]$Bucket = "overlink-papersage-desktop-updates-prod"
)

$ErrorActionPreference = "Stop"
if (-not $env:AWS_ACCESS_KEY_ID -or -not $env:AWS_SECRET_ACCESS_KEY) {
  throw "Set AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY (R2 token) first."
}

$tmp = Join-Path ([System.IO.Path]::GetTempPath()) "r2-hop-$Tag"
New-Item -ItemType Directory -Force -Path $tmp | Out-Null

# Updater artifacts are attached to the GitHub release; mirror exactly what
# the old workflow published: metadata (no-store) + packages/blockmaps
# (immutable).
$patterns = @("latest.yml", "latest-mac.yml", "latest-linux.yml", "*.exe", "*.dmg", "*.zip",
  "*.AppImage", "*.deb", "*.exe.blockmap", "*.dmg.blockmap", "*.zip.blockmap", "*.AppImage.blockmap")

$downloaded = @()
foreach ($pattern in $patterns) {
  gh release download $Tag --pattern $pattern --dir $tmp --clobber 2>$null
  $found = Get-ChildItem -Path $tmp -Filter $pattern -File -ErrorAction SilentlyContinue
  foreach ($file in $found) {
    if ($downloaded -notcontains $file.Name) { $downloaded += $file.Name }
  }
}

# Metadata declares the package paths; anything referenced must exist locally.
foreach ($metadataFile in @("latest.yml", "latest-mac.yml", "latest-linux.yml")) {
  $metadataPath = Join-Path $tmp $metadataFile
  if (-not (Test-Path $metadataPath)) { continue }
  $path = (Select-String -LiteralPath $metadataPath -Pattern '^path:\s*["'']?([^"''\r\n]+)' | Select-Object -First 1).Matches.Groups[1].Value.Trim()
  if (-not $path) { throw "Updater metadata does not declare a path: $metadataFile" }
  foreach ($name in @($path, "$path.blockmap")) {
    if (-not (Test-Path (Join-Path $tmp $name))) { throw "Missing updater asset: $name" }
    if ($downloaded -notcontains $name) { $downloaded += $name }
  }
}

if (-not $downloaded) { throw "No updater assets found for $Tag." }
foreach ($file in $downloaded) {
  $localPath = Join-Path $tmp $file
  $cacheControl = if ($file -like "latest*.yml") { "no-store" } else { "public, max-age=31536000, immutable" }
  Write-Host "upload $file (cache-control: $cacheControl)"
  aws s3 cp $localPath "s3://$Bucket/$file" --endpoint-url $Endpoint --cache-control $cacheControl --only-show-errors
}
Write-Host "Done. Old clients will now offer 1.14.0 from R2; after they hop, the bucket can be retired."
