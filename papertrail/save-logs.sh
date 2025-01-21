#!/bin/bash

# map containerId to serviceName
declare -A container_map

refresh_container_map() {
	state_json=$(curl -s "$BALENA_SUPERVISOR_ADDRESS/v2/state/status?apikey=$BALENA_SUPERVISOR_API_KEY")
	while IFS= read -r container; do
		container_id=$(echo "$container" | jq -r '.containerId' | cut -c1-12)
		service_name=$(echo "$container" | jq -r '.serviceName')
		container_map["$container_id"]="$service_name"
	done < <(echo "$state_json" | jq -c '.containers[]')
}

# populate container_map
refresh_container_map

# Initialize the last refresh time
last_refresh_time=$(date +%s)

# loop to process logs
while true; do
	curl -X POST -H "Content-Type: application/json" --no-buffer --data '{"follow":true,"all":true,"format":"short"}' "$BALENA_SUPERVISOR_ADDRESS/v2/journal-logs?apikey=$BALENA_SUPERVISOR_API_KEY" \
	| while IFS= read -r line; do
		current_time=$(date +%s)
		
		# refresh container_map every 60 seconds
		if (( current_time - last_refresh_time >= 60 )); then
			echo "Refreshing container map at $(date)"
			refresh_container_map
			last_refresh_time=$current_time
		fi

		container_id=$(echo "$line" | grep -oE '[a-f0-9]{12}')
		
		# check if container_id is not empty and exists in the map
		if [[ -n "$container_id" && -n "${container_map[$container_id]}" ]]; then
			# replace container_id with service_name
			line=${line//$container_id/${container_map[$container_id]}}
		fi
		
		# send modified log line to papertrail
		curl -s -u :$PAPERTRAIL_TOKEN -H "content-type:text/plain" -d "${line}" "https://logs.collector.solarwinds.com/v1/log";
	done
done