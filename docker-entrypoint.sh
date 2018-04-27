#!/usr/bin/env bash

isCommand() {
  for cmd in "service" \
             "intergration"
  do
    if [ -z "${cmd#"$1"}" ]; then
      return 0
    fi
  done

  return 1
}

# check if the first argument passed in looks like a flag
if [ "${1:0:1}" = '-' ]; then
  set -- /sbin/tini -- honeycomb "$@"

# check if the first argument passed in is honeycomb
elif [ "$1" = 'honeycomb' ]; then
  set -- /sbin/tini -- "$@"

# check if the first argument passed in matches a known command
elif isCommand "$1"; then
  set -- /sbin/tini -- honeycomb "$@"
fi

exec "$@"
