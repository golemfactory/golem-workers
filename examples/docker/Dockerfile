FROM python:3.8-slim

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
    	openssh-client

RUN pip install golem-workers

EXPOSE 8000

CMD ["uvicorn", "--host", "0.0.0.0", "golem_workers.entrypoints.web.main:app"]
