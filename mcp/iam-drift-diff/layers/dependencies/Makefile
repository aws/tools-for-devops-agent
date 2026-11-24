# Dependencies layer build.
#
# fastmcp pulls in pydantic, whose pydantic_core is a COMPILED extension. A
# plain `pip install` on the build host installs a wheel for the HOST platform,
# so building on macOS (or arm64) yields a binary the x86_64 Lambda runtime
# cannot import, failing at init with:
#   ModuleNotFoundError: No module named 'pydantic_core._pydantic_core'
#
# Pin the target platform and Python version so the correct manylinux wheels are
# fetched regardless of build host. --only-binary=:all: is required with
# --platform and makes a missing wheel a loud failure rather than a silent
# host-targeted source build.
#
# Keep in sync with the function Runtime/Architectures in template.yaml
# (python3.12 / x86_64).

.PHONY: build-DependenciesLayer
build-DependenciesLayer:
	mkdir -p "$(ARTIFACTS_DIR)/python"
	python3 -m pip install \
		-r requirements.txt \
		--require-hashes \
		--platform manylinux2014_x86_64 \
		--python-version 3.12 \
		--implementation cp \
		--only-binary=:all: \
		--upgrade \
		-t "$(ARTIFACTS_DIR)/python"
