<#
Creates weapon_ar15\meta\weaponanimations.meta from the game's own weaponanimations.meta:
every animation-set entry of WEAPON_CARBINERIFLE is copied under the name WEAPON_AR15, so the
AR-15 uses exactly the carbine rifle animations (aim, fire, reload, cover, first person).

  1. OpenIV or CodeWalker: export  update\update.rpf\common\data\ai\weaponanimations.meta
  2. PowerShell:  .\make_weaponanimations.ps1 -Vanilla C:\path\to\weaponanimations.meta
#>
param(
    [Parameter(Mandatory = $true)][string]$Vanilla,
    [string]$Base = 'WEAPON_CARBINERIFLE',
    [string]$Name = 'WEAPON_AR15',
    [string]$Out = (Join-Path $PSScriptRoot '..\weapon_ar15\meta\weaponanimations.meta')
)

$src = New-Object System.Xml.XmlDocument
$src.Load((Resolve-Path -LiteralPath $Vanilla).Path)

$dst = New-Object System.Xml.XmlDocument
$null = $dst.AppendChild($dst.CreateXmlDeclaration('1.0', 'UTF-8', $null))
$root = $dst.AppendChild($dst.CreateElement('CWeaponAnimationsSets'))
$sets = $root.AppendChild($dst.CreateElement('WeaponAnimationsSets'))

$count = 0
foreach ($set in $src.SelectNodes('/CWeaponAnimationsSets/WeaponAnimationsSets/Item')) {
    $entry = $set.SelectSingleNode("WeaponAnimations/Item[@key='$Base']")
    if ($null -eq $entry) { continue }
    $newSet = $sets.AppendChild($dst.CreateElement('Item'))
    $newSet.SetAttribute('key', $set.GetAttribute('key'))
    $fallback = $set.SelectSingleNode('Fallback')
    if ($null -ne $fallback) { $null = $newSet.AppendChild($dst.ImportNode($fallback, $true)) }
    $anims = $newSet.AppendChild($dst.CreateElement('WeaponAnimations'))
    $copy = $dst.ImportNode($entry, $true)
    $copy.SetAttribute('key', $Name)
    $null = $anims.AppendChild($copy)
    $count++
}
if ($count -eq 0) { throw "No '$Base' entries found in $Vanilla" }

$outPath = [System.IO.Path]::GetFullPath($Out)
$settings = New-Object System.Xml.XmlWriterSettings
$settings.Indent = $true
$settings.Encoding = New-Object System.Text.UTF8Encoding($false)
$writer = [System.Xml.XmlWriter]::Create($outPath, $settings)
$dst.Save($writer)
$writer.Close()
Write-Host "Wrote $count animation sets for $Name to $outPath"
