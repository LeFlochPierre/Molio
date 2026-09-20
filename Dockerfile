FROM python:3.12-slim
WORKDIR /app
COPY . /app
RUN useradd --create-home isoform && chown -R isoform:isoform /app
USER isoform
EXPOSE 8000
CMD ["python", "-m", "cyp_pipeline.sentinel_server", "--bind", "0.0.0.0"]
