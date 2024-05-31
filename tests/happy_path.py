import requests


def main():
    headers = {
        "accept": "application/json",
        "Content-Type": "application/json",
    }

    response = requests.get(
        "http://127.0.0.1:8000/offers",
        headers=headers,
        json={
            "payload": {},
        },
    )
    assert (
        response.status_code == 200
    ), f"{response.status_code} http://127.0.0.1:8000/offers {response.text}"
    proposal_ids = [r["proposal_id"] for r in response.json()]
    print(proposal_ids)

    response = requests.post(
        "http://127.0.0.1:8000/cluster",
        headers=headers,
        json={
            "id_": "happyPath",
            "node_config": {
                "subnet_tag": "public",
                "demand": {
                    "image_hash": "1a0f2d0b1512018445a028c8f46151969ef8ddaaf3435ae118d3071d",
                    # "image_tag": "string",
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
            },
        },
    )
    assert (
        response.status_code == 200
    ), f"{response.status_code} http://127.0.0.1:8000/cluster {response.text}"

    response = requests.post(
        "http://127.0.0.1:8000/cluster/happyPath/node",
        headers=headers,
        json={
            "proposal_ids": proposal_ids,
        },
    )
    assert (
        response.status_code == 200
    ), f"{response.status_code} http://127.0.0.1:8000/cluster/happyPath/node {response.text}"

    print(f"{response.status_code}: {response.text}")


if __name__ == "__main__":
    main()
