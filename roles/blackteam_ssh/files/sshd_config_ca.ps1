# Add the CA settings to sshd_config ABOVE the first "Match" block (anything
# after a Match line only applies to that match). Idempotent.
$ErrorActionPreference = 'Stop'

$cfg = 'C:\ProgramData\ssh\sshd_config'
$add = @(
    'TrustedUserCAKeys __PROGRAMDATA__/ssh/vault-ca.pub',
    'AuthorizedPrincipalsFile __PROGRAMDATA__/ssh/auth_principals/%u'
)

$lines = @(Get-Content $cfg)
$missing = @($add | Where-Object { $lines -notcontains $_ })
if ($missing.Count -eq 0) { $Ansible.Changed = $false; return }

$i = [array]::FindIndex($lines, [Predicate[string]]{ $args[0] -match '^\s*Match\s' })
if ($i -gt 0) { $lines = $lines[0..($i - 1)] + $missing + $lines[$i..($lines.Count - 1)] }
elseif ($i -eq 0) { $lines = $missing + $lines }
else { $lines += $missing }
Set-Content -Encoding ascii $cfg $lines
