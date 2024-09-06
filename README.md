# golem-workers

### Getting started

The are multiple ways to start interacting with golem-workers.
Below are two of the most common ways to start it.

#### Docker example

Docker example will take care for installation, proper processes setup (`golem-workers` web server and `golem-node` service) and their basic configuration.
Note that because of decentralized fashion, `golem-node` needs a few moments to gather information from the Golem Network, during that time, amount of returned proposals can be impacted.

To run docker example, checkout the repository and go to `examples/docker` directory, or directly copy its contents to your preferred destination. 

1. Make sure that [Docker](https://www.docker.com/) is running on your machine and your current user have access to it.
 
2. Build and start docker compose project.
   ```shell
   docker compose up -d --build
   ```

3. Prepare some funds for Golem's free test network. 
   Note that this step is needed mostly once per `yagna-data` volume. 

   ```shell
   docker compose exec golem-node yagna payment fund
   ```
   
4. Golem-workers can be interacted with web api at http://localhost:8000.
   It's [OpenApi Specification](https://www.openapis.org/) is available at http://localhost:8000/docs or http://localhost:8000/redoc

#### Web server

1. Install golem-workers via:
   ```shell
   pip install golem-workers
   ```
   This step should install `yagna` binary for the next steps.

2. Start `golem-node` instance. This will occupy your terminal session, so it's best to do it in separate session.
   ```shell
   yagna service run
   ```

3. Prepare some funds for Golem's free test network. 
   Note that this step is needed mostly once per `golem-node` installation. 

   ```shell
   yagna payment fund
   ```

4. Create new `golem-node` application token
   ```shell
   yagna app-key create <your-token-name>
   ```
   and put generated app-key into the `.env` file in the current directory
   ```dotenv
   YAGNA_APPKEY=<your-application-token>
   ```

5. If you want to use Golem Reputation put new entry in `.env` file in the current directory
   ```dotenv
   GLOBAL_CONTEXTS=["golem_reputation.ReputationService"]
   ```

6. Start golem-workers web server instance
   ```shell
   uvicorn golem_workers.entrypoints.web.main:app
   ```
   
7. Golem-workers can be interacted with web api at http://localhost:8000.
   It's [OpenApi Specification](https://www.openapis.org/) is available at http://localhost:8000/docs or http://localhost:8000/redoc
