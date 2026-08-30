#Requires -RunAsAdministrator

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$Server,

    [ValidateNotNullOrEmpty()]
    [string]$ShareName = 'PrintQ',

    [ValidateNotNullOrEmpty()]
    [string]$PrinterName = 'PrintQ',

    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$DriverName
)

$ErrorActionPreference = 'Stop'
$portName = "\\$Server\$ShareName"

$driver = Get-PrinterDriver -Name $DriverName -ErrorAction SilentlyContinue
if (-not $driver) {
    $available = Get-PrinterDriver |
        Sort-Object Name |
        ForEach-Object { "  - $($_.Name)" }
    throw "Printer driver '$DriverName' is not installed. Install it first and use its exact name.`nInstalled drivers:`n$($available -join "`n")"
}

$existingPrinter = Get-Printer -Name $PrinterName -ErrorAction SilentlyContinue
if ($existingPrinter) {
    if ($existingPrinter.PortName -eq $portName -and
        $existingPrinter.DriverName -eq $DriverName) {
        Write-Host "Printer '$PrinterName' is already configured correctly."
        exit 0
    }

    throw "Printer '$PrinterName' already exists with port '$($existingPrinter.PortName)' and driver '$($existingPrinter.DriverName)'. Remove or rename it, then run this installer again."
}

if (-not (Get-PrinterPort -Name $portName -ErrorAction SilentlyContinue)) {
    Add-PrinterPort -Name $portName
    Write-Host "Created authenticated SMB port $portName"
}

Add-Printer -Name $PrinterName -DriverName $DriverName -PortName $portName
Write-Host "Installed '$PrinterName' using '$DriverName' through $portName"
Write-Host "Windows will authenticate to Samba with the signed-in domain identity."
