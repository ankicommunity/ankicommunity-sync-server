FROM python:3.9-slim-buster
# Set default environment variables.
ARG ANKISYNCD_ROOT=/opt/ankisyncd \
    ANKISYNCD_DATA_ROOT=/srv/ankisyncd \
    ANKISYNCD_PORT=27701 \
    ANKISYNCD_BASE_URL=/sync/ \
    ANKISYNCD_BASE_MEDIA_URL=/msync/ \
    ANKISYNCD_AUTH_DB_PATH=auth.db \
    ANKISYNCD_SESSION_DB_PATH=session.db \
    ANKISYNCD_USER=app

RUN useradd -m ${ANKISYNCD_USER} && \
    mkdir ${ANKISYNCD_DATA_ROOT} && \
    chown ${ANKISYNCD_USER}:${ANKISYNCD_USER} ${ANKISYNCD_DATA_ROOT}

USER ${ANKISYNCD_USER}
WORKDIR ${ANKISYNCD_ROOT}

COPY --chown=${ANKISYNCD_USER}:${ANKISYNCD_USER} src/ .
RUN pip3 install --user -r requirements.txt

ENV ANKISYNCD_HOST=0.0.0.0 \
	ANKISYNCD_PORT=${ANKISYNCD_PORT} \
	ANKISYNCD_DATA_ROOT=${ANKISYNCD_DATA_ROOT} \
	ANKISYNCD_BASE_URL=${ANKISYNCD_BASE_URL} \
	ANKISYNCD_BASE_MEDIA_URL=${ANKISYNCD_BASE_MEDIA_URL} \
	ANKISYNCD_AUTH_DB_PATH=${ANKISYNCD_DATA_ROOT}/${ANKISYNCD_AUTH_DB_PATH} \
	ANKISYNCD_SESSION_DB_PATH=${ANKISYNCD_DATA_ROOT}/${ANKISYNCD_SESSION_DB_PATH} \
    PATH=${PATH}:${HOME}/.local/bin

EXPOSE ${ANKISYNCD_PORT}

CMD ["python3", "-m", "ankisyncd"]

HEALTHCHECK --interval=60s --timeout=3s CMD python -c "import requests; requests.get('http://127.0.0.1:${ANKISYNCD_PORT}/')"