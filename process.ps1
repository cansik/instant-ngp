param (
    $path,
    $scale=16,
    [Switch]$render=$false,
    $time=5,
    $fps=24,
    $width=1280,
    $height=720,
    $spp=8,
    [Switch]$smoothing=$true
)

function op($name, $c) {
    if($c) {
        return $name
    }
    return ""
}

if (-not(Test-path "$path/transforms.json" -PathType leaf))
{
	if (Test-path "$path/cameras.xml" -PathType leaf)
	{
		echo "converting agisoft camera file..."
		# convert agisoft
		python scripts/agi2nerf.py --xml_in "$path/cameras.xml" --out "$path/transforms.json" --imgtype png --imgfolder "$path"
	} else {
		echo "aligning images with colmap..."
		# run colmap2nerf
		python scripts/colmap2nerf.py --colmap_matcher sequential --run_colmap --aabb_scale $scale --images "$path"
	}
}

# run testbed or renderer
if ($render) {
    echo "rendering..."
    $render_name = Split-Path "$path" -Leaf
    $smp = op "--camera-smoothing" $smoothing
    python scripts/render.py --scene "$path" --n_seconds $time --fps $fps --render_name "$render_name" --width $width --height $height --spp $spp $smp
} else {
	$add_args = ""

	if (Test-path "$path/base.msgpack" -PathType leaf)
	{
		echo "loading snapshot $path/base.msgpack"
		python scripts/run.py --mode nerf --scene "$path" --load_snapshot "$path/base.msgpack" --near_distance 0.01 --gui --width 720 --height 720
	} else {
		echo "training..."
		python scripts/run.py --mode nerf --scene "$path" --save_snapshot "$path/base.msgpack" --near_distance 0.01 --train --n_steps 20000 --width 720 --height 720 --gui
	}
}
