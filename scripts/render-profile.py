"""Emit a complete imager stdin profile; stdin mode ignores extension CLI flags."""
import json
import os
import sys

with open(sys.argv[1]) as stream:
    profile = json.load(stream)
profile["input"]["systemExtensions"] = [{"imageRef": image} for image in sys.argv[2:]]
# sd-boot ignores machine.install.extraKernelArgs, so node opt-ins must be baked into the UKI here.
kernel_args = os.environ.get("KERNEL_ARGS", "").split()
if kernel_args:
    profile.setdefault("customization", {})["extraKernelArgs"] = kernel_args
json.dump(profile, sys.stdout)
