#!/bin/bash
# Usage: ./repro.sh /path/to/OpenDebugAD7
# Leaves the processes running. Kill OpenDebugAD7 afterwards.
send() { printf 'Content-Length: %d\r\n\r\n%s' ${#1} "$1"; }
{
  send '{"seq":1,"type":"request","command":"initialize","arguments":{"adapterID":"cppdbg","pathFormat":"path"}}'
  send '{"seq":2,"type":"request","command":"launch","arguments":{"program":"/bin/sleep","args":["12345"],"cwd":"/","MIMode":"gdb"}}'
  send '{"seq":3,"type":"request","command":"configurationDone"}'
  sleep 5
} | "$1" &> /dev/null &
sleep 15
pgrep -a -x OpenDebugAD7;
pgrep -a -x gdb;
pgrep -a -f 'sleep 12345'
