#!/bin/sh

VERSION=20.x

cd bindings/clang
wget https://raw.githubusercontent.com/llvm/llvm-project/release/$VERSION/clang/bindings/python/clang/cindex.py
wget https://raw.githubusercontent.com/llvm/llvm-project/release/$VERSION/clang/bindings/python/clang/__init__.py
cd -
