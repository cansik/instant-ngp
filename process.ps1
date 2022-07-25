param ($path, $scale=16)

if(-not(Test-path "$path/transform.json" -PathType leaf))
{
    # run colmap2nerf
    python scripts/colmap2nerf.py --colmap_matcher sequential --run_colmap --aabb_scale $scale --images "$path"
}

# run testbed
 .\build\testbed.exe --scene "$path"