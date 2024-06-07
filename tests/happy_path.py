import requests


def main():
    headers = {
        "accept": "application/json",
        "Content-Type": "application/json",
    }

    response = requests.post(
        "http://127.0.0.1:8000/get-proposals",
        headers=headers,
        json={},
    )
    assert response.status_code == 200, f"{response.status_code} GET-PROPOSALS {response.text}"
    proposal_ids = [r["proposal_id"] for r in response.json()]
    print(proposal_ids)
    assert len(proposal_ids) > 0

    response = requests.post(
        "http://127.0.0.1:8000/delete-cluster",
        headers=headers,
        json={
            "cluster_id": "happyPath",
        },
    )
    assert response.status_code in (
        200,
        404,
    ), f"{response.status_code} DELETE-CLUSTER {response.text}"

    response = requests.post(
        "http://127.0.0.1:8000/create-cluster",
        headers=headers,
        json={
            "cluster_id": "happyPath",
            "node_config": {
                "node_config_data": {
                    "subnet_tag": "public",
                    "demand": {
                        # "image_hash": "1a0f2d0b1512018445a028c8f46151969ef8ddaaf3435ae118d3071d",
                        "image_tag": "blueshade/ray-on-golem:0.11.0a2-py3.10.13-ray2.9.3",
                        # "capabilities": [
                        #     "vpn",
                        #     "inet",
                        # ],
                        # "outbound_urls": [],
                        "min_mem_gib": 1,
                        "min_cpu_threads": 1,
                        "min_storage_gib": 1,
                        "max_cpu_threads": 20,
                        "runtime": "vm",
                    },
                    "budget_control": {
                        "per_cpu_expected_usage": {
                            "cpu_load": 0.9,
                            "duration_hours": 0.5,
                            "max_cost": 1.5,
                        },
                        "max_start_price": 0.5,
                        "max_cpu_per_hour_price": 0.5,
                        "max_env_per_hour_price": 0.5,
                        "payment_interval_hours": {
                            "minimal": 12,
                        },
                    },
                }
            },
        },
    )
    assert response.status_code == 200, f"{response.status_code} CREATE-CLUSTER {response.text}"

    response = requests.post(
        "http://127.0.0.1:8000/create-nodes",
        headers=headers,
        json={
            "cluster_id": "happyPath",
            "proposal_ids": proposal_ids[:10],
        },
    )
    assert response.status_code == 200, f"{response.status_code} CREATE-NODES {response.text}"

    print(f"{response.status_code}: {response.text}")


if __name__ == "__main__":
    main()
