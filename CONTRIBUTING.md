# golem-workers contributing

## Development environment

### Prerequisites

Golem-workers uses [poetry](https://python-poetry.org/) for project management and [poethepoet](https://github.com/nat-n/poethepoet) for task running.
To install those tools you can use [pipx](https://pipx.pypa.io/stable/):

```shell
pipx install poetry poethepoet
```

or just [pip](https://pip.pypa.io/en/stable/):
```shell
pip install poetry poethepoet
```

Also, golem-workers needs some instance of [golem-node](https://github.com/golemfactory/yagna) to interact with Golem Network.
Download newest stable version `golem-requestor-<your OS type>` and make sure that its binaries are available from your `PATH` environment variable. 

### Installation

1. Clone the repo
   ```shell
   git clone https://github.com/golemfactory/golem-workers
   ```
2. Go inside of the newly created directory
   ```shell
   cd golem-workers
   ```
3. Install project dependencies
   ```shell
   poetry install
   ```

### Running

Follow web server chapter in [README.md](README.md) file.
