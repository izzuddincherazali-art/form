FROM python:3.12-slim
WORKDIR /app
COPY server.py bootstrap.py ./
COPY public ./public
RUN mkdir /data && chown nobody:nogroup /data
USER nobody
ENV HOST=0.0.0.0 PORT=8000 DATABASE_PATH=/data/sessions.sqlite3
EXPOSE 8000
CMD ["python", "bootstrap.py"]
