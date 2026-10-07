param(
    [Parameter(Mandatory = $true)][string]$AdminPassword,
    [Parameter(Mandatory = $true)][string]$DomainsJson
)

# Configure hMailServer domains/accounts via its COM API. Idempotent.
# Data comes in as JSON ($DomainsJson), so this file stays plain PowerShell.
$ErrorActionPreference = 'Stop'

$domains = $DomainsJson | ConvertFrom-Json

$hmail = New-Object -ComObject hMailServer.Application
$hmail.Authenticate("Administrator", $AdminPassword) | Out-Null

foreach ($d in $domains) {
    try { $domain = $hmail.Domains.ItemByName($d.name) } catch { $domain = $null }
    if (-not $domain) {
        $domain = $hmail.Domains.Add()
        $domain.Name = $d.name
    }
    $domain.Active = $true
    $domain.Save()

    foreach ($a in $d.accounts) {
        try { $acct = $domain.Accounts.ItemByAddress($a.address) } catch { $acct = $null }
        if (-not $acct) {
            $acct = $domain.Accounts.Add()
            $acct.Address = $a.address
        }
        $acct.Password = $a.password
        $acct.Active = $true
        $acct.Save()
    }
}

Write-Output "APPLIED"
