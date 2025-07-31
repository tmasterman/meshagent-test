FROM meshagent/cli:latest

ARG MANIFEST_JSON
LABEL meshagent.service.manifest="$MANIFEST_JSON"

ENTRYPOINT meshagent chatbot service --agent-name='imagebot' --image-generation=gpt-image-1
