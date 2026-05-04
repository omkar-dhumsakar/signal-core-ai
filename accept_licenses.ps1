$proc = New-Object System.Diagnostics.Process
$proc.StartInfo.FileName = "flutter.bat"
$proc.StartInfo.Arguments = "doctor --android-licenses"
$proc.StartInfo.UseShellExecute = $false
$proc.StartInfo.RedirectStandardInput = $true
$proc.StartInfo.RedirectStandardOutput = $true
$proc.StartInfo.RedirectStandardError = $true
$proc.StartInfo.CreateNoWindow = $true
$proc.Start() | Out-Null
Start-Sleep -Seconds 5
for ($i=0; $i -lt 10; $i++) {
    $proc.StandardInput.WriteLine("y")
    Start-Sleep -Seconds 2
}
$proc.WaitForExit()
