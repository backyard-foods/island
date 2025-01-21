#!/bin/bash

# Query supervisor state endpoint to map containerId to serviceName
state_json=$(curl -s "$BALENA_SUPERVISOR_ADDRESS/v2/state/status?apikey=$BALENA_SUPERVISOR_API_KEY")

declare -A container_map
while IFS= read -r container; do
	container_id=$(echo "$container" | jq -r '.containerId' | cut -c1-12)
	service_name=$(echo "$container" | jq -r '.serviceName')
	container_map["$container_id"]="$service_name"
done < <(echo "$state_json" | jq -c '.containers[]')

while true;
do
	curl -X POST -H "Content-Type: application/json" --no-buffer --data '{"follow":true,"all":true,"format":"short"}' "$BALENA_SUPERVISOR_ADDRESS/v2/journal-logs?apikey=$BALENA_SUPERVISOR_API_KEY" \
	| while read -r line ;
		do
			container_id=$(echo "$line" | grep -oE '[a-f0-9]{12}')
			
			# Check if the container_id is not empty and exists in the map
			if [[ -n "$container_id" && -n "${container_map[$container_id]}" ]]; then
				# Replace the container ID with the service name
				line=${line//$container_id/${container_map[$container_id]}}
			fi
			
			# Send the modified log line to papertrail
			curl -s -u :$PAPERTRAIL_TOKEN -H "content-type:text/plain" -d "${line}" "https://logs.collector.solarwinds.com/v1/log";
		done
done