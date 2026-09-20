"""Emit a complete imager stdin profile; stdin mode ignores extension CLI flags."""
import json
import sys

with open(sys.argv[1]) as stream:
    profile = json.load(stream)
profile["input"]["systemExtensions"] = [{"imageRef": image} for image in sys.argv[2:]]
json.dump(profile, sys.stdout)
