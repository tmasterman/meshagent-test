FROM meshagent/cli:latest

ENTRYPOINT ["meshagent", "chatbot", "service", "--agent-name=codebot", "--model=codex-mini-latest", "--local-shell", "--toolkit=ui", "--rule=you may only write files inside the /data folder, everything else is read only. You should use the display_document tool to show files to users. strip the leading /data when showing files with display_document since the display_document tool expects a path relative to /data. If the user mentions a file that they uploaded,  it should be inside the /data folder since the root of the room storage is mounted to /data."]
