param ($path, $scale=16, [Switch]$render=$false, $time=5, $fps=24, $width=1280, $height=720)

if (-not(Test-path "$path/transforms.json" -PathType leaf))
{
    # run colmap2nerf
    python scripts/colmap2nerf.py --colmap_matcher sequential --run_colmap --aabb_scale $scale --images "$path"
}


# run testbed or renderer
if ($render) {
    $render_name = Split-Path "$path" -Leaf
    python scripts/render.py --scene "$path" --n_seconds $time --fps $fps --render_name "$render_name" --width $width --height $height
} else {
    .\build\testbed.exe --scene "$path"
}