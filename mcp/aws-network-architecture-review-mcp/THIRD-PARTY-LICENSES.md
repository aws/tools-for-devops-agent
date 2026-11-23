# Third-party licenses

This project is licensed under Apache-2.0 (see the repository `LICENSE`). The
deployed function also includes the third-party components below.

## Lambda layers

| Component | Version | License | Source |
|---|---|---|---|
| AWS Lambda Web Adapter (`LambdaAdapterLayerX86`, AWS-published layer) | layer version 24 | Apache-2.0 | https://github.com/awslabs/aws-lambda-web-adapter |

## Python dependencies (dependencies layer)

`layers/dependencies/requirements.txt` pins the direct dependencies (`fastmcp`,
`boto3`). This table is the full set pip resolved from that file on 2026-10-26
for Python 3.12 / `manylinux2014_x86_64`, the same target the layer build uses.
Licenses are as declared in each package's metadata. Transitive versions aren't
locked yet (see CHANGELOG), so a later build can resolve newer versions;
regenerate this table when the pins or the lock file change.

| Package | Version | License | Source |
|---|---|---|---|
| aiofile | 3.12.3 | Apache-2.0 | https://github.com/mosquito/aiofile |
| annotated-types | 0.8.0 | MIT | https://github.com/annotated-types/annotated-types |
| anyio | 4.15.1 | MIT | https://github.com/agronholm/anyio |
| attrs | 26.1.0 | MIT | https://github.com/python-attrs/attrs |
| authlib | 1.9.1 | BSD | https://github.com/authlib/authlib |
| beartype | 0.23.1 | MIT | https://github.com/beartype/beartype |
| boto3 | 1.43.118 | Apache-2.0 | https://github.com/boto/boto3 |
| botocore | 1.43.119 | Apache-2.0 | https://github.com/boto/botocore |
| cachetools | 7.2.6 | MIT | https://github.com/tkem/cachetools/ |
| caio | 0.12.10 | Apache-2.0 | https://github.com/mosquito/caio/ |
| certifi | 2026.10.23 | MPL-2.0 | https://github.com/certifi/python-certifi |
| cffi | 2.1.1 | MIT-0 | https://github.com/python-cffi/cffi |
| click | 8.5.0 | BSD-3-Clause | https://github.com/pallets/click/ |
| cryptography | 50.0.2 | Apache-2.0 OR BSD-3-Clause | https://github.com/pyca/cryptography |
| cyclopts | 5.3.1 | Apache-2.0 | https://github.com/BrianPugh/cyclopts |
| dnspython | 2.9.0 | ISC | https://www.dnspython.org |
| docstring_parser | 0.18.0 | MIT | https://github.com/rr-/docstring_parser |
| email-validator | 2.3.0 | Unlicense | https://github.com/JoshData/python-email-validator |
| exceptiongroup | 1.3.1 | MIT | https://github.com/agronholm/exceptiongroup |
| fastmcp | 3.4.11 | Apache-2.0 | https://gofastmcp.com |
| fastmcp-slim | 3.4.11 | Apache-2.0 | https://gofastmcp.com |
| griffelib | 2.4.1 | ISC | https://mkdocstrings.github.io/griffe |
| h11 | 0.16.0 | MIT | https://github.com/python-hyper/h11 |
| httpcore | 1.0.9 | BSD-3-Clause | https://www.encode.io/httpcore/ |
| httpx | 0.28.1 | BSD | https://github.com/encode/httpx |
| httpx-sse | 0.4.3 | MIT | https://github.com/florimondmanca/httpx-sse |
| idna | 3.20 | BSD-3-Clause | https://github.com/kjd/idna |
| jaraco.classes | 3.4.0 | MIT | https://github.com/jaraco/jaraco.classes |
| jaraco.context | 6.1.2 | MIT | https://github.com/jaraco/jaraco.context |
| jaraco.functools | 4.6.0 | MIT | https://github.com/jaraco/jaraco.functools |
| jmespath | 1.1.0 | MIT | https://github.com/jmespath/jmespath.py |
| joserfc | 1.7.7 | BSD | https://github.com/authlib/joserfc |
| jsonref | 1.1.0 | MIT | https://github.com/gazpachoking/jsonref |
| jsonschema | 4.26.0 | MIT | https://github.com/python-jsonschema/jsonschema |
| jsonschema-path | 0.5.0 | Apache-2.0 | https://github.com/p1c2u/jsonschema-path |
| jsonschema-specifications | 2025.9.1 | MIT | https://github.com/python-jsonschema/jsonschema-specifications |
| keyring | 25.7.0 | MIT | https://github.com/jaraco/keyring |
| markdown-it-py | 4.2.0 | MIT | https://github.com/executablebooks/markdown-it-py |
| mcp | 1.30.0 | MIT | https://modelcontextprotocol.io |
| mdurl | 0.1.2 | MIT | https://github.com/executablebooks/mdurl |
| more-itertools | 11.2.1 | MIT | https://github.com/more-itertools/more-itertools |
| openapi-pydantic | 0.6.0 | MIT | https://github.com/mike-oakley/openapi-pydantic |
| opentelemetry-api | 1.45.1 | Apache-2.0 | https://github.com/open-telemetry/opentelemetry-python/tree/main/opentelemetry-api |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause | https://github.com/pypa/packaging |
| pathable | 0.6.0 | Apache-2.0 | https://github.com/p1c2u/pathable |
| platformdirs | 4.13.5 | MIT | https://github.com/tox-dev/platformdirs |
| py-key-value-aio | 0.4.6 | Apache-2.0 |  |
| pycparser | 3.12 | BSD-3-Clause | https://github.com/eliben/pycparser |
| pydantic | 2.14.1 | MIT | https://github.com/pydantic/pydantic |
| pydantic-settings | 2.16.1 | MIT | https://github.com/pydantic/pydantic-settings |
| pydantic_core | 2.50.1 | MIT | https://github.com/pydantic |
| pygments | 2.21.0 | BSD-2-Clause | https://pygments.org |
| pyjwt | 2.15.1 | MIT | https://github.com/jpadilla/pyjwt |
| pyperclip | 1.11.0 | BSD | https://github.com/asweigart/pyperclip |
| python-dateutil | 2.9.0.post0 | BSD-3-Clause OR Apache-2.0 | https://github.com/dateutil/dateutil |
| python-dotenv | 1.2.4 | BSD-3-Clause | https://github.com/theskumar/python-dotenv |
| python-multipart | 0.0.32 | Apache-2.0 | https://github.com/Kludex/python-multipart |
| pyyaml | 6.0.3 | MIT | https://github.com/yaml/pyyaml |
| referencing | 0.37.0 | MIT | https://github.com/python-jsonschema/referencing |
| rich | 15.0.0 | MIT | https://github.com/Textualize/rich |
| rich-rst | 2.2.0 | MIT | https://github.com/wasi-master/rich-rst |
| rpds-py | 2026.9.1 | MIT | https://github.com/crate-py/rpds |
| s3transfer | 0.19.3 | Apache-2.0 | https://github.com/boto/s3transfer |
| six | 1.17.0 | MIT | https://github.com/benjaminp/six |
| sse-starlette | 3.6.0 | BSD-3-Clause | https://github.com/sysid/sse-starlette |
| starlette | 1.10.0 | BSD-3-Clause | https://github.com/Kludex/starlette |
| typing-inspection | 0.4.4 | MIT | https://github.com/pydantic/typing-inspection |
| typing_extensions | 4.16.0 | PSF-2.0 | https://github.com/python/typing_extensions |
| uncalled-for | 0.4.1 | MIT | https://github.com/chrisguidry/uncalled-for |
| urllib3 | 2.8.0 | MIT | https://github.com/urllib3/urllib3 |
| uvicorn | 0.54.0 | BSD-3-Clause | https://uvicorn.dev/ |
| watchfiles | 1.3.0 | MIT | https://github.com/samuelcolvin/watchfiles |
| websockets | 17.3 | BSD-3-Clause | https://github.com/python-websockets/websockets |
