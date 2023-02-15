set /A frames=100

echo %~n1
PowerShell -Command "conda activate ngp; clear; sfextract %1 --frame-count %frames% --output %~n1 --format png --cpu-count 4 --force-cpu-count"