# Temporal-AI-Workflows

docker compose -f docker-compose-postgres.yml up -d

temporal operator cluster health --address localhost:7233

temporal operator namespace create -n default

python process_pdf.py "s3://temporal-dev/files/sample.pdf"

