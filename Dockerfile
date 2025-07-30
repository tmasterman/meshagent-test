FROM meshagent/python-sdk-slim:latest

ARG MANIFEST_JSON
LABEL meshagent.service.manifest="$MANIFEST_JSON"

RUN apt-get update && apt-get install -y curl

ENTRYPOINT meshagent chatbot service --agent-name='imagebot' --image-generation=gpt-image-1
