FROM meshagent/python-sdk-slim:latest

ARG MANIFEST_JSON
LABEL meshagent.service.manifest="$MANIFEST_JSON"

ENTRYPOINT meshagent chatbot service --agent-name='chatbot'