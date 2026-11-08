param(
    [Parameter(Mandatory=$true)][string]$Path,
    [Parameter(Mandatory=$true)][string]$CertificateThumbprint,
    [string]$TimestampServer = 'https://timestamp.digicert.com'
)
$ErrorActionPreference = 'Stop'
$target = (Resolve-Path -LiteralPath $Path).Path
if ([IO.Path]::GetExtension($target) -notin '.exe','.dll','.msi') { throw 'Choose one Windows release binary.' }
if ($CertificateThumbprint -notmatch '^[A-Fa-f0-9]{40}$') { throw 'Use the thumbprint of an installed code-signing certificate.' }
$certificate = Get-Item -LiteralPath "Cert:\CurrentUser\My\$CertificateThumbprint"
if (-not $certificate.HasPrivateKey) { throw 'The selected certificate has no available private key.' }
if (-not ($certificate.EnhancedKeyUsageList | Where-Object { $_.ObjectId.Value -eq '1.3.6.1.5.5.7.3.3' })) { throw 'The certificate is not valid for code signing.' }
if ($certificate.NotAfter -le (Get-Date)) { throw 'The signing certificate has expired.' }
$uri = [Uri]$TimestampServer
if ($uri.Scheme -ne 'https') { throw 'Use an HTTPS timestamp service.' }
if ((Get-AuthenticodeSignature -LiteralPath $target).Status -ne 'NotSigned') { throw 'Sign a fresh unsigned build; preserve existing vendor signatures and the unsigned reproducibility artifacts.' }
$unsignedHash = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant()
$signature = Set-AuthenticodeSignature -LiteralPath $target -Certificate $certificate -HashAlgorithm SHA256 -TimestampServer $TimestampServer
if ($signature.Status -ne 'Valid') { throw "Signature validation failed: $($signature.Status)" }
$verified = Get-AuthenticodeSignature -LiteralPath $target
if ($verified.Status -ne 'Valid' -or $verified.SignerCertificate.Thumbprint -ne $certificate.Thumbprint) { throw 'The signed file did not verify against the selected identity.' }
$signedHash = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant()
$filename = [IO.Path]::GetFileName($target)
$manifestPath = Join-Path ([IO.Path]::GetDirectoryName($target)) 'build_manifest.json'
if (Test-Path -LiteralPath $manifestPath) {
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json -AsHashtable
    if ($manifest.binary_files.ContainsKey($filename)) {
        $manifest.binary_files[$filename] = $signedHash
        if (-not $manifest.ContainsKey('authenticode')) { $manifest.authenticode = @{} }
        $manifest.authenticode[$filename] = @{ unsigned_sha256=$unsignedHash; signed_sha256=$signedHash; certificate_thumbprint=$certificate.Thumbprint }
        $temporary = $manifestPath + '.signing.tmp'
        try {
            [IO.File]::WriteAllText($temporary, ($manifest | ConvertTo-Json -Depth 32), [Text.UTF8Encoding]::new($false))
            Move-Item -LiteralPath $temporary -Destination $manifestPath -Force
        } finally {
            if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary }
        }
    }
}
[PSCustomObject]@{ File=$filename; Status=$verified.Status.ToString(); Publisher=$verified.SignerCertificate.Subject; UnsignedSHA256=$unsignedHash; SHA256=$signedHash } | ConvertTo-Json
