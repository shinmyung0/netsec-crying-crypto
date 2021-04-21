FROM  alpine:latest
RUN   adduser -S -D -H -h /xmrig miner
COPY ./xmrig .
USER miner
WORKDIR    /xmrig
ENTRYPOINT  ["./xmrig"]
