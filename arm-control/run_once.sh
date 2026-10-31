#!/bin/sh
set -eu
exec docker exec -it --user ubuntu --env HOME=/home/ubuntu armpi_pro /bin/zsh -lc 'source /home/ubuntu/armpi_pro/src/armpi_pro_bringup/scripts/source_env.bash >/dev/null; exec /usr/bin/python3 /home/ubuntu/share/tmp/forward_wait_left_demo.py --cycles 1'
