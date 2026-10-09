#!/bin/zsh
# Mathcode launcher (macOS): double-click this file in Finder.
#
# It starts the API (port 8100) and the web interface (port 5180) and opens the
# browser. The first run sets everything up (the Python environment in
# backend/.venv and the frontend packages); later runs start in seconds.
# Everything is free and runs on this Mac. To stop: Ctrl+C here, or close the window.
#
# From a terminal: ./Mathcode.command (MATHCODE_NO_BROWSER=1 skips the browser)

# 1. Work from the project folder: the one this file is in.
cd "${0:A:h}" || exit 1

# 2. Finder doesn't use your Terminal's PATH: add Homebrew's folders, where
#    python3.14 and node usually live.
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

API_PORT=8100
WEB_PORT=5180
URL="http://localhost:$WEB_PORT"

say() { print -P "\n%B$*%b"; }
fail() {
  print -u2 "\n$*"
  read "?Aperte Enter para fechar esta janela. "
  exit 1
}
in_use() { lsof -nP -iTCP:"$1" -sTCP:LISTEN > /dev/null 2>&1; }
api_up() { curl -s "http://127.0.0.1:$API_PORT/api/health" | grep -q '"status"'; }
open_browser() { [[ -n $MATHCODE_NO_BROWSER ]] || open "$URL"; }

# 3. Already running? Then just open the browser.
if in_use $API_PORT && in_use $WEB_PORT && api_up; then
  say "O Mathcode já está rodando: abrindo $URL"
  open_browser
  exit 0
fi
in_use $API_PORT && fail "A porta $API_PORT está ocupada por outro programa. Feche-o e tente de novo."
in_use $WEB_PORT && fail "A porta $WEB_PORT está ocupada por outro programa. Feche-o e tente de novo."

# 4. The backend in backend/.venv (Python 3.14): installed the first time, and
#    again whenever pyproject.toml changes (after a `git pull`, say).
MARKER="backend/.venv/.mathcode-installed"
if [[ ! -f $MARKER || backend/pyproject.toml -nt $MARKER ]] ||
  ! backend/.venv/bin/python -c 'import fastapi, uvicorn, sympy' 2> /dev/null; then
  say "Preparando o backend (só na primeira vez; leva um minuto)..."
  if [[ ! -x backend/.venv/bin/python ]]; then
    command -v python3.14 > /dev/null ||
      fail "O Mathcode precisa do Python 3.14, que é gratuito: https://www.python.org/downloads/"
    python3.14 -m venv backend/.venv || fail "Não foi possível criar o ambiente Python (backend/.venv)."
  fi
  backend/.venv/bin/python -m pip install --quiet --upgrade pip &&
    backend/.venv/bin/python -m pip install --quiet -e "backend[dev]" ||
    fail "A instalação do backend falhou: veja as mensagens acima."
  touch "$MARKER"
fi

# 5. The frontend packages (Node): the first time, and when package-lock.json
#    changes. `npm ci` also copies Swagger UI into the backend (/api/docs).
command -v npm > /dev/null || fail "O Mathcode precisa do Node.js, que é gratuito: https://nodejs.org"
if [[ ! -d frontend/node_modules || frontend/package-lock.json -nt frontend/node_modules ]]; then
  say "Preparando a interface (só na primeira vez)..."
  npm --prefix frontend ci --silent || fail "A instalação do frontend falhou: veja as mensagens acima."
  touch frontend/node_modules
fi

# 6. On exit (Ctrl+C or a closed window), both servers stop together.
stop() {
  [[ -n $WEB_PID ]] && kill $WEB_PID 2> /dev/null
  [[ -n $API_PID ]] && kill $API_PID 2> /dev/null
  wait 2> /dev/null
}
trap stop EXIT
trap 'exit 0' INT TERM HUP

say "Iniciando o Mathcode..."
backend/.venv/bin/uvicorn app.main:app --app-dir backend --port $API_PORT --log-level warning &
API_PID=$!
# exec: the PID is Vite's own, so stopping it does not leave Vite running.
(cd frontend && exec node_modules/.bin/vite --clearScreen false --logLevel warn) &
WEB_PID=$!

# 7. Wait for the API (its workers import SymPy) and the interface to answer.
for _ in {1..60}; do
  if api_up && curl -s -o /dev/null "$URL"; then
    READY=1
    break
  fi
  kill -0 $API_PID 2> /dev/null || fail "A API parou ao iniciar: veja as mensagens acima."
  kill -0 $WEB_PID 2> /dev/null || fail "A interface parou ao iniciar: veja as mensagens acima."
  sleep 1
done
[[ -n $READY ]] || fail "O Mathcode não respondeu em 60 segundos."

say "Mathcode aberto em $URL"
print "Mantenha esta janela aberta enquanto usa o Mathcode;"
print "aperte Ctrl+C ou feche a janela para parar."
open_browser
wait $API_PID $WEB_PID
