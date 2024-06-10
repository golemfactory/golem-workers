# cluster-api

Before running fill `SSH_KEY_USER` and `SSH_KEY_PATH` in `clusterapi/main.py`

To start CLuster API

```bash
fastapi dev clusterapi/main.py
```

TO run test script

```bash
python tests/happy_path.py 
```

```bash
curl -X 'POST' \
  'http://127.0.0.1:8000/get-cluster' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "cluster_id": "happyPath"
}'
```
