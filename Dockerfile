FROM alpine:latest

RUN apk add --no-cache curl unzip

RUN curl -L -o xray.zip https://github.com/XTLS/Xray-core/releases/latest/download/Xray-linux-64.zip \
    && unzip xray.zip \
    && mv xray /usr/local/bin/xray \
    && chmod +x /usr/local/bin/xray \
    && rm -f xray.zip

COPY config.json /etc/xray/config.json

ENTRYPOINT ["xray", "-config", "/etc/xray/config.json"]
