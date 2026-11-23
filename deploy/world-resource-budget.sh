#!/bin/sh
# Legacy cgroup-v1 supplement; run as root after the service becomes ready.
# Also applies scheduler settings to the existing group without a game restart.
set -eu
memory_group=/sys/fs/cgroup/memory/system.slice/mlogent-world.service
process_group=/sys/fs/cgroup/pids/system.slice/mlogent-world.service

# The v1 soft limit is a reclaim hint, not a guaranteed reservation or throttle.
echo 536870912 > "$memory_group/memory.soft_limit_in_bytes"
# Prefer reclaiming file cache over swapping this latency-sensitive service.
# This is a preference under pressure, not a RAM reservation or swap ban.
if [ -f "$memory_group/memory.swappiness" ]; then
    echo 10 > "$memory_group/memory.swappiness"
fi
if [ -f "$memory_group/memory.memsw.limit_in_bytes" ]; then
    # Total resident+swapped charge; this is NOT a separate 200-MiB swap cap.
    echo 943718400 > "$memory_group/memory.memsw.limit_in_bytes"
fi

for process_id in $(cat "$process_group/cgroup.procs"); do
    if [ -d "/proc/$process_id" ]; then
        /usr/bin/renice -n 5 -p "$process_id" >/dev/null || [ ! -d "/proc/$process_id" ]
        /usr/bin/ionice -c 2 -n 7 -p "$process_id" || [ ! -d "/proc/$process_id" ]
        if [ -d "/proc/$process_id" ]; then
            echo 400 > "/proc/$process_id/oom_score_adj"
        fi
    fi
done
