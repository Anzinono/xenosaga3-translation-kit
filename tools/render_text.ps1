# Renders text with a Windows font (GDI+) as a grayscale mask (white on black) into a BMP file.
# Usage: powershell -NoProfile -File tools\render_text.ps1 -Text "NEW GAME" -Font "Arial Narrow" -Size 17 -Out mask.bmp [-Bold]
# Size is in pixels (em height). The image is cropped to the text (2 px margin).
param(
    [Parameter(Mandatory = $true)][string]$Text,
    [string]$Font = "Arial",
    [float]$Size = 16,
    [Parameter(Mandatory = $true)][string]$Out,
    [switch]$Bold
)
Add-Type -AssemblyName System.Drawing
$style = if ($Bold) { [System.Drawing.FontStyle]::Bold } else { [System.Drawing.FontStyle]::Regular }
$f = New-Object System.Drawing.Font($Font, $Size, $style, [System.Drawing.GraphicsUnit]::Pixel)
if ($f.Name -ne $Font) { throw "Font '$Font' not found (substitute: $($f.Name))" }
$tmp = New-Object System.Drawing.Bitmap(1, 1)
$g = [System.Drawing.Graphics]::FromImage($tmp)
$fmt = [System.Drawing.StringFormat]::GenericTypographic
$sz = $g.MeasureString($Text, $f, 10000, $fmt)
$g.Dispose(); $tmp.Dispose()
$w = [int][Math]::Ceiling($sz.Width) + 4
$h = [int][Math]::Ceiling($f.GetHeight()) + 4
$bmp = New-Object System.Drawing.Bitmap($w, $h, [System.Drawing.Imaging.PixelFormat]::Format24bppRgb)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.Clear([System.Drawing.Color]::Black)
$g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAlias
$g.DrawString($Text, $f, [System.Drawing.Brushes]::White, 2, 2, $fmt)
$g.Dispose()
$bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Bmp)
$bmp.Dispose()
