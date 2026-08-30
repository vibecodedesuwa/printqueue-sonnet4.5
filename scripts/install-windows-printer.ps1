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

if ($driver.MajorVersion -ge 4) {
    throw "Printer driver '$DriverName' is a Type 4/filter-pipeline driver (MajorVersion $($driver.MajorVersion)). PrintQ's client-rendered Samba port requires a Type 3 driver (MajorVersion 3), such as the Windows 'MS Publisher Color Printer' PostScript driver. Install a compatible Type 3 driver, then run this installer with its exact name."
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
    try {
        Add-PrinterPort -Name $portName
        Write-Host "Created authenticated SMB port $portName"
    }
    catch {
        # The Local Port monitor can retain a UNC port that Get-PrinterPort does
        # not enumerate. Treat ERROR_ALREADY_EXISTS as success; Add-Printer can
        # still bind to that valid port name.
        if ($_.Exception.HResult -eq -2147024713 -or
            $_.FullyQualifiedErrorId -match '0x800700b7|ResourceExists') {
            Write-Host "Authenticated SMB port $portName already exists."
        }
        else {
            throw
        }
    }
}

Add-Printer -Name $PrinterName -DriverName $DriverName -PortName $portName
Write-Host "Installed '$PrinterName' using '$DriverName' through $portName"
Write-Host "Windows will authenticate to Samba with the signed-in domain identity."
