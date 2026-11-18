#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
check_dir=$(mktemp -d /private/tmp/toilet-coordination.XXXXXX)
trap 'rm -rf "$check_dir"' EXIT
xcrun swiftc -parse-as-library -module-cache-path "$check_dir/module-cache" \
  ios/ToiletMap/App/RuntimeConfig.swift \
  ios/ToiletMap/Data/Models.swift \
  ios/ToiletMap/Data/ToiletQueryFilters.swift \
  ios/ToiletMap/Services/APIClient.swift \
  ios/ToiletMap/Data/ToiletRepository.swift \
  ios/Tests/RequestCoordinationChecks.swift \
  -o "$check_dir/checks"
"$check_dir/checks"
