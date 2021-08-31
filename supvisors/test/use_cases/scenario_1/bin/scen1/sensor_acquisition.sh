#!/bin/bash

test_dir=$(dirname "$(readlink -f "$0")")

$test_dir/common.sh ${SUPERVISOR_PROCESS_NAME}
