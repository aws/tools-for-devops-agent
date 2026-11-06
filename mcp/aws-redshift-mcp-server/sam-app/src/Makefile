# Invoked by `sam build` (BuildMethod: makefile in template.yaml).
#
# Installs uv and mcp-proxy targeting manylinux2014_aarch64 / Python 3.13
# wheels directly via pip -- no Docker/Finch/container needed, because
# every dependency in this tree (uv, mcp-proxy, and transitive deps like
# cryptography and pydantic-core) publishes prebuilt manylinux wheels for
# arm64. This makes the deployment buildable on any machine with Python,
# including CI runners and customer laptops without container access.
#
# ARTIFACTS_DIR is provided by `sam build`.
build-RedshiftMcpFunction:
	python3 -m pip install \
		--platform manylinux2014_aarch64 \
		--python-version 3.13 \
		--implementation cp \
		--abi cp313 \
		--only-binary=:all: \
		--target "$(ARTIFACTS_DIR)" \
		-r requirements.txt
	cp run.sh "$(ARTIFACTS_DIR)/run.sh"
	chmod 755 "$(ARTIFACTS_DIR)/run.sh"
