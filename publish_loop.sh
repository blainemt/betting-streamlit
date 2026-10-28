#!/bin/bash
# Re-publish snapshots at 8:25, 13:50 and 15:40 local time.
while true; do
  hm=$(date +%H%M)
  if [ "$hm" = "0825" ] || [ "$hm" = "1350" ] || [ "$hm" = "1540" ]; then
    cd /workspace/betting-streamlit && bash publish.sh >> /tmp/publish.log 2>&1
    sleep 61
  fi
  sleep 30
done
