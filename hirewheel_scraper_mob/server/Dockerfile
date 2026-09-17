# Server image with everything the hosted-login flow needs.
#
# The Playwright base image already carries Chromium and its libraries; on top of
# it we add the virtual display stack (Xvfb) and the VNC bridge (x11vnc,
# websockify, noVNC) that lets a student complete Hirewheel's login from their
# phone. Those processes are started per login and torn down straight after.
FROM mcr.microsoft.com/playwright/python:v1.61.0-noble

RUN apt-get update && apt-get install -y --no-install-recommends \
        xvfb \
        x11vnc \
        websockify \
        novnc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY hwcore ./hwcore
COPY hwserver ./hwserver
COPY tests ./tests

ENV HW_DATA_DIR=/data \
    HW_LOGIN_MODE=novnc \
    HW_NOVNC_DIR=/usr/share/novnc \
    HW_HOST=0.0.0.0 \
    HW_PORT=8000

VOLUME ["/data"]
EXPOSE 8000

# HW_SECRET_KEY and HW_INVITE_CODE must be supplied at run time.
CMD ["python", "-m", "hwserver"]
