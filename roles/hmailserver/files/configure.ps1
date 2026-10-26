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

# Create (or fetch) a mailbox and point its auth at the given AD account.
function Set-AdMailbox($domain, $address, $netbios, $sam) {
    try { $acct = $domain.Accounts.ItemByAddress($address) } catch { $acct = $null }
    if (-not $acct) {
        $acct = $domain.Accounts.Add()
        $acct.Address = $address
    }
    $acct.IsAD       = $true
    $acct.ADDomain   = $netbios
    $acct.ADUsername = $sam
    $acct.Active     = $true
    $acct.Save()
}

foreach ($d in $domains) {
    try { $domain = $hmail.Domains.ItemByName($d.name) } catch { $domain = $null }
    if (-not $domain) {
        $domain = $hmail.Domains.Add()
        $domain.Name = $d.name
    }
    $domain.Active = $true
    $domain.Save()

    # --- Bulk: create an AD-authenticated mailbox for every AD user ----------
    $fromAD = ($d.PSObject.Properties.Name -contains 'from_ad') -and $d.from_ad
    if ($fromAD) {
        $netbios = $env:USERDOMAIN   # NetBIOS name of the running domain (e.g. ACME)
        # Enabled user accounts only (UAC bit 2 = disabled). Override via ad_filter.
        $filter = '(&(objectCategory=person)(objectClass=user)(!(userAccountControl:1.2.840.113556.1.4.803:=2)))'
        if (($d.PSObject.Properties.Name -contains 'ad_filter') -and $d.ad_filter) {
            $filter = $d.ad_filter
        }
        $searcher = [ADSISearcher]$filter
        $searcher.PageSize = 1000
        $searcher.PropertiesToLoad.Add('samAccountName') | Out-Null

        foreach ($r in $searcher.FindAll()) {
            $sam = [string]$r.Properties['samaccountname'][0]
            if (-not $sam) { continue }
            $address = ($sam.ToLower()) + '@' + $d.name
            Set-AdMailbox $domain $address $netbios $sam
        }
    }

    # --- Explicit accounts (still works alongside from_ad) -------------------
    foreach ($a in $d.accounts) {
        try { $acct = $domain.Accounts.ItemByAddress($a.address) } catch { $acct = $null }
        if (-not $acct) {
            $acct = $domain.Accounts.Add()
            $acct.Address = $a.address
        }

        $hasAD = ($a.PSObject.Properties.Name -contains 'ad_username') -and $a.ad_username
        if ($hasAD) {
            $acct.IsAD       = $true
            $acct.ADDomain   = $a.ad_domain
            $acct.ADUsername = $a.ad_username
        } else {
            $acct.IsAD    = $false
            $acct.Password = $a.password
        }

        $acct.Active = $true
        $acct.Save()
    }
}

Write-Output "APPLIED"
