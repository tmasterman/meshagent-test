FROM meshagent/python-sdk:latest

RUN pip install --no-cache-dir meshagent-otel

COPY . /src

WORKDIR /src

ENTRYPOINT [ "python3", "main.py" ] 
