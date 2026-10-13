#!/bin/zsh
# Run the content-commit gate detached, with a done marker a Monitor can wait on:
#   nohup zsh scripts/gate_detached.sh <message-file> <tag> [--after-mint] > /dev/null 2>&1 &
# Writes $PKINV_GATE_DIR/chain_<tag>.log and touches $PKINV_GATE_DIR/gate_<tag>.done at the end
# (success = HEAD advanced). Use a FRESH tag per launch: a stale done marker from an earlier
# launch makes a waiter return instantly with the old log.
ROOT=$(cd "$(dirname "$0")/.." && pwd); cd "$ROOT" || exit 1
G=${PKINV_GATE_DIR:-/tmp/pakemis-gate}; mkdir -p "$G"
MSG=${1:?message file}; TAG=${2:?tag}; shift 2
rm -f "$G/gate_$TAG.done"
zsh scripts/gate_chain.sh "$MSG" "$@" > "$G/chain_$TAG.log" 2>&1
echo "chain exit $?" >> "$G/chain_$TAG.log"
touch "$G/gate_$TAG.done"
