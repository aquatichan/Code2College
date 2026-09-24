# Server image with everything the hosted-login flow needs.
#
# The Playwright base image already carries Chromium and its libraries; on top of
# it we add a virtual display (Xvfb), a VNC server for it (x11vnc), and the noVNC
# page that renders it in the app. The API serves that page and relays its
# WebSocket itself, so the container exposes a single port. The display exists
# only while someone is signing in.
FROM mcr.microsoft.com/playwright/python:v1.61.0-noble

RUN apt-get update && apt-get install -y --no-install-recommends \
        xvfb \
        x11vnc \
        novnc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv

COPY requirements.txt .
# Pin Playwright to the image's version: its bundled Chromium only matches that
# exact release, and a newer pip install would look for a browser that isn't there.
ENV PIP_BREAK_SYSTEM_PACKAGES=1
RUN pip install --no-cache-dir -r requirements.txt "playwright==1.61.0"

COPY hwcore ./hwcore
COPY hwserver ./hwserver

ENV HW_DATA_DIR=/data \
    HW_LOGIN_MODE=novnc \
    HW_NOVNC_DIR=/usr/share/novnc \
    HW_HOST=0.0.0.0 \
    HW_PORT=8000 \
    PYTHONUNBUFFERED=1

VOLUME ["/data"]
EXPOSE 8000

# HW_SECRET_KEY and HW_INVITE_CODE must be supplied at run time, as secrets.
CMD ["python", "-m", "hwserver"]
