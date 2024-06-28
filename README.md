# cluster-api

## Getting started

Currently cluster-api is only available for used via direct installation from git repository.
Here are some steps to prepare local development environment.

### Prerequisites

cluster-api uses [poetry](https://python-poetry.org/) for project management and [poethepoet](https://github.com/nat-n/poethepoet) for task running.
To install those tools you can use [pipx](https://pipx.pypa.io/stable/):

```shell
pipx install poetry poethepoet
```

or just [pip](https://pip.pypa.io/en/stable/):
```shell
pip install poetry poethepoet
```

Also, cluster-api needs some instance of [golem-node](https://github.com/golemfactory/yagna) to interact with Golem Network.
Download newest stable version `golem-requestor-<your OS type>` and make sure that its binaries are available from your `PATH` environment variable. 

Optionally, if you want to use simpler startup, install [Docker](https://www.docker.com/).

### Installation

1. Clone the repo
   ```shell
   git clone https://github.com/golemfactory/cluster-api
   ```
2. Go inside of the newly created directory
   ```shell
   cd cluster-api
   ```
3. Install project dependencies
   ```shell
   poetry install
   ```

### Running

The are multiple ways to run cluster-api instance.
Below are two of the simplest ways to start it.

#### Docker example

1. Start [Docker](https://www.docker.com/) instance and make sure that is running and the current user have access to it.
 
2. Go to docker example directory.
   ```shell
   cd examples/docker
   ```

3. Build and start compose project in the background.
   Note that because of decentralized fashion, `golem-node` needs a moment to gather information from the Golem Network and amount of returned proposals can be impacted.
   ```shell
   docker compose up -d --build
   ```

4. Prepare some funds for Golem's free test network. 
   Note that this step is needed mostly once per `yagna-data` volume. 

   ```shell
   docker compose exec golem-node yagna payment fund
   ```

#### Development

1. Start `golem-node` instance in dedicated terminal session.
   Note that because of decentralized fashion, `golem-node` needs a moment to gather information from the Golem Network and amount of returned proposals can be impacted.
   ```shell
   yagna service start
   ```

2. Prepare some funds for Golem's free test network. 
   Note that this step is needed mostly once per `golem-node` installation. 

   ```shell
   yagna payment fund
   ```

3. Create new `golem-node` application token
   ```shell
   yagna app-key create <your-token-name>
   ```
   and create `.env` file at the root of the repo and put there
   ```dotenv
   YAGNA_APPKEY=<your-application-token>
   ```

3. Start cluster-api instance
   ```shell
   poetry run fastapi dev golem_cluster_api/main.py --no-reload
   ```

## Usage

Cluster-api can be interacted with web api at http://localhost:8000.
It's [OpenApi Specification](https://www.openapis.org/) is available at http://localhost:8000/docs