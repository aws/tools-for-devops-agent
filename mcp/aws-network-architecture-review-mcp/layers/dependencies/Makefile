# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

# Dependencies layer build.
#
# fastmcp pulls in pydantic, whose pydantic_core is a compiled extension. A plain
# `pip install` on a build host installs a wheel for the HOST platform, so
# building on macOS (or arm64 Linux) yields a binary the x86_64 Lambda runtime
# cannot import. Pin the target platform and Python version so the correct
# manylinux wheels are fetched regardless of the build host. --only-binary=:all:
# is required with --platform and makes a missing wheel a loud failure.
#
# --upgrade is intentionally NOT used: it would pull newer transitive versions
# at each build. A fully hash-locked requirements file (pip-compile
# --generate-hashes, resolved in a python3.12 / manylinux2014_x86_64
# environment) + --require-hashes is the tracked follow-up; see CHANGELOG.
#
# Keep these values in sync with Runtime and Architectures in template.yaml
# (python3.12 / x86_64).

.PHONY: build-DependenciesLayer
build-DependenciesLayer:
	mkdir -p "$(ARTIFACTS_DIR)/python"
	python3 -m pip install \
		-r requirements.txt \
		--platform manylinux2014_x86_64 \
		--python-version 3.12 \
		--implementation cp \
		--only-binary=:all: \
		-t "$(ARTIFACTS_DIR)/python"
