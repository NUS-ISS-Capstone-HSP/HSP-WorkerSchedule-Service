#!/usr/bin/env bash
set -euo pipefail

python3 -m grpc_tools.protoc -I . --python_out=. --grpc_python_out=. rpc/echo/v1/echo.proto
