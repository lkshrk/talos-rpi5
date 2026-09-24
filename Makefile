TALOS_VERSION = v1.14.1
IMAGE_REVISION =
SBCOVERLAY_VERSION = 7d04484be2beb4b1fca56538d2b6d07e7d58681f

REGISTRY ?= ghcr.io
REGISTRY_USERNAME ?= lkshrk
TAG ?= $(TALOS_VERSION)$(if $(IMAGE_REVISION),-rpi5.$(IMAGE_REVISION))
# Retain the existing runtime extension; override EXTENSIONS= for no extensions.
EXTENSIONS ?= ghcr.io/siderolabs/gvisor:20250505.0@sha256:d7503b59603f030b972ceb29e5e86979e6c889be1596e87642291fee48ce380c

TALOS_REPOSITORY = https://github.com/siderolabs/talos.git
SBCOVERLAY_REPOSITORY = https://github.com/talos-rpi5/sbc-raspberrypi5.git
CHECKOUTS_DIRECTORY := $(CURDIR)/checkouts
PATCHES_DIRECTORY := $(CURDIR)/patches
ARTIFACTS := $(CURDIR)/_out
# The overlay DTBs must match Talos's stock kernel, not an independently bumped pkgs tag.
PKGS = $(shell sed -n 's/^PKGS ?= //p' "$(CHECKOUTS_DIRECTORY)/talos/Makefile")
INSTALLER_IMAGE = $(REGISTRY)/$(REGISTRY_USERNAME)/talos-rpi5-installer:$(TAG)
IMAGER = talos-rpi5-imager:$(TAG)

.PHONY: help image-version checkouts patches test overlay installer verify release clean
help:
	@echo "checkouts : Fetch pinned Talos and Pi boot overlay sources"
	@echo "patches   : Apply Pi boot-selection and firmware/U-Boot compatibility fixes"
	@echo "test      : Run the focused Linux boot-selection regression tests"
	@echo "overlay   : Build the existing Pi U-Boot overlay with stock kernel DTBs"
	@echo "installer : Build local installer/raw artifacts; does not publish"
	@echo "verify    : Check installer architecture/version and required Pi boot assets"
	@echo "release   : Publish the installer artifact as $(INSTALLER_IMAGE)"
	@echo "clean     : Remove generated checkouts and artifacts"

image-version:
	@echo "$(TAG)"

checkouts:
	git clone -c advice.detachedHead=false --depth 1 --branch "$(TALOS_VERSION)" "$(TALOS_REPOSITORY)" "$(CHECKOUTS_DIRECTORY)/talos"
	git clone --no-checkout "$(SBCOVERLAY_REPOSITORY)" "$(CHECKOUTS_DIRECTORY)/sbc-raspberrypi5"
	git -C "$(CHECKOUTS_DIRECTORY)/sbc-raspberrypi5" checkout --detach "$(SBCOVERLAY_VERSION)"

patches:
	cd "$(CHECKOUTS_DIRECTORY)/talos" && git apply --check "$(PATCHES_DIRECTORY)/siderolabs/talos/0001-rpi5-loader-conf-fallback.patch"
	cd "$(CHECKOUTS_DIRECTORY)/talos" && git apply "$(PATCHES_DIRECTORY)/siderolabs/talos/0001-rpi5-loader-conf-fallback.patch"
	cd "$(CHECKOUTS_DIRECTORY)/talos" && git apply --check "$(PATCHES_DIRECTORY)/siderolabs/talos/0002-image-overlay-assets.patch"
	cd "$(CHECKOUTS_DIRECTORY)/talos" && git apply "$(PATCHES_DIRECTORY)/siderolabs/talos/0002-image-overlay-assets.patch"
	cd "$(CHECKOUTS_DIRECTORY)/sbc-raspberrypi5" && git apply --check "$(PATCHES_DIRECTORY)/talos-rpi5/sbc-raspberrypi5/0001-mainline-pi5-boot-compatibility.patch"
	cd "$(CHECKOUTS_DIRECTORY)/sbc-raspberrypi5" && git apply "$(PATCHES_DIRECTORY)/talos-rpi5/sbc-raspberrypi5/0001-mainline-pi5-boot-compatibility.patch"

test:
	docker run --rm --platform linux/arm64 --cpus=2 --memory=2g \
		-v "$(CHECKOUTS_DIRECTORY)/talos:/src" -w /src \
		-v talos-rpi5-go-mod:/go/pkg/mod -v talos-rpi5-go-build:/root/.cache/go-build \
		-e GOMAXPROCS=2 golang:1.26.5 \
		go test -p 1 ./internal/app/machined/pkg/runtime/v1alpha1/bootloader/sdboot

overlay:
	test -n "$(PKGS)"
	mkdir -p "$(ARTIFACTS)"
	$(MAKE) -C "$(CHECKOUTS_DIRECTORY)/sbc-raspberrypi5" target-sbc-raspberrypi5 \
		PKGS_PREFIX=ghcr.io/siderolabs PKGS=$(PKGS) PLATFORM=linux/arm64 \
		TARGET_ARGS="--output=type=oci,dest=$(ARTIFACTS)/overlay,tar=false"

installer:
	test -f "$(ARTIFACTS)/overlay/index.json"
	$(MAKE) -C "$(CHECKOUTS_DIRECTORY)/talos" initramfs \
		ARTIFACTS="$(ARTIFACTS)" TAG=$(TALOS_VERSION) \
		INSTALLER_ARCH=arm64 PLATFORM=linux/arm64 PUSH=false
	$(MAKE) -C "$(CHECKOUTS_DIRECTORY)/talos" target-installer-base \
		TAG=$(TALOS_VERSION) INSTALLER_ARCH=arm64 PLATFORM=linux/arm64 PUSH=false \
		TARGET_ARGS="--output=type=oci,dest=$(ARTIFACTS)/installer-base,tar=false"
	$(MAKE) -C "$(CHECKOUTS_DIRECTORY)/talos" target-imager \
		TAG=$(TALOS_VERSION) INSTALLER_ARCH=arm64 PLATFORM=linux/arm64 PUSH=false \
		TARGET_ARGS="--load --tag=$(IMAGER)"
	python3 scripts/render-profile.py profiles/installer.json $(EXTENSIONS) | \
	docker run --rm -i --platform linux/arm64 \
		-v "$(ARTIFACTS):/assets:ro" -v "$(ARTIFACTS):/out" \
		"$(IMAGER)" -
	python3 scripts/render-profile.py profiles/metal.json $(EXTENSIONS) | \
	docker run --rm -i --platform linux/arm64 --privileged \
		-v "$(ARTIFACTS):/assets:ro" -v "$(ARTIFACTS):/out" \
		"$(IMAGER)" -

verify:
	python3 scripts/verify-artifacts.py "$(ARTIFACTS)" "$(TALOS_VERSION)"
	bash scripts/verify-raw-image.sh "$(ARTIFACTS)/metal-arm64.raw.zst"

release: verify
	crane push "$(ARTIFACTS)/installer-arm64.tar" "$(INSTALLER_IMAGE)"

clean:
	rm -rf "$(CHECKOUTS_DIRECTORY)" "$(ARTIFACTS)"
