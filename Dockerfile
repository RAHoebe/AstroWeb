FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 ASTROWEB_DATA=/data
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg libexpat1 && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 astroweb && useradd --uid 10001 --gid astroweb --no-create-home astroweb \
    && mkdir /data && chown astroweb:astroweb /data
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
ENV SUNPY_CONFIGDIR=/tmp/astroweb-sunpy MPLCONFIGDIR=/tmp/astroweb-matplotlib XDG_CONFIG_HOME=/tmp/astroweb-config XDG_CACHE_HOME=/tmp/astroweb-cache
COPY astroweb ./astroweb
COPY astroweb/sunpyrc /etc/xdg/sunpy/sunpyrc
COPY README.md README.en.md LICENSE THIRD_PARTY.md ./
USER 10001:10001
VOLUME ["/data"]
EXPOSE 8090
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8090/api/health', timeout=3)"
CMD ["python", "-m", "astroweb", "serve", "--host", "0.0.0.0", "--port", "8090"]
