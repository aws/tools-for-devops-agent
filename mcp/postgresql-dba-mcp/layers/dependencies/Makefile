RDS_CA_URL := https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem
RDS_CA_SHA256 := e5bb2084ccf45087bda1c9bffdea0eb15ee67f0b91646106e466714f9de3c7e3

build-DependenciesLayer:
	rm -rf python/ "$(ARTIFACTS_DIR)/python/"
	mkdir -p python/ "$(ARTIFACTS_DIR)/python/"
	pip3 install --disable-pip-version-check --no-compile --requirement requirements.txt --target python/ --platform manylinux2014_x86_64 --python-version 3.12 --only-binary=:all: --implementation cp
	curl --fail --silent --show-error --location "$(RDS_CA_URL)" --output python/rds-global-bundle.pem
	python3 verify_sha256.py python/rds-global-bundle.pem "$(RDS_CA_SHA256)"
	cp -R python/. "$(ARTIFACTS_DIR)/python/"
