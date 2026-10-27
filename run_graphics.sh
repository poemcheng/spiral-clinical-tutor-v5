#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
if [ ! -x .venv-graphics/bin/python ]; then
  python3 -m venv .venv-graphics
  .venv-graphics/bin/python -m pip install -r requirements-graphics.txt
fi
echo '電腦圖學平台：http://127.0.0.1:8715'
echo '首次管理員帳密：runtime/graphics/initial-admin.txt（或自訂 GRAPHICS_HOME）'
exec .venv-graphics/bin/python -m uvicorn backend.graphics_server:app --host 127.0.0.1 --port 8715
