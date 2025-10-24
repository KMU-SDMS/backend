#!/bin/bash
# -----------------------------------------------------------------------------
# AWS Lambda Layer 빌드 스크립트
# -----------------------------------------------------------------------------
# 이 스크립트는 AWS Lambda와 호환되는 Python 라이브러리를 설치하여
# 'layer' 폴더를 생성합니다.
# requirements.txt 파일이 변경되었을 때만 실행하면 됩니다.
# -----------------------------------------------------------------------------

# 스크립트 실행 중 에러가 발생하면 즉시 중단합니다.
set -e

# 1. 이전 layer 폴더가 있다면 깨끗하게 삭제합니다.
echo "🧹 Cleaning up old layer directory..."
rm -rf layer

# 2. AWS Lambda (Linux)와 호환되는 라이브러리를 'layer' 폴더에 설치합니다.
echo "📦 Building new Python dependencies layer for AWS Lambda..."
python3 -m pip install \
    --platform manylinux2014_x86_64 \
    --target=./layer/python \
    --implementation cp \
    --python-version 3.11 \
    --only-binary=:all: --upgrade \
    -r requirements.txt

# 3. 성공 메시지를 출력합니다.
echo "✅ Layer build complete. You are now ready to deploy!"