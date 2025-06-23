# پایه ایمیج آلپاین سبک
FROM alpine:latest

# نصب curl و unzip برای دانلود Xray
RUN apk add --no-cache curl unzip

# دانلود آخرین نسخه Xray-core لینوکس 64 بیت
RUN curl -L -o xray.zip https://github.com/XTLS/Xray-core/releases/latest/download/Xray-linux-64.zip \
    && unzip xray.zip \
    && mv xray /usr/local/bin/xray \
    && chmod +x /usr/local/bin/xray \
    && rm -f xray.zip

# کپی فایل کانفیگ به داخل کانتینر
COPY config.json /etc/xray/config.json

# فرمان اجرای Xray با کانفیگ مشخص
ENTRYPOINT ["xray", "-config", "/etc/xray/config.json"]