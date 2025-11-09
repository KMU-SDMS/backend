# AL2023 기반 (glibc >= 2.27)
FROM public.ecr.aws/lambda/provided:al2023

WORKDIR /var/task

# 시스템 패키지 설치 (python3.11 포함)
RUN dnf -y update && \
    dnf -y install \
      python3.11 \
      python3.11-devel \
      python3.11-pip \
      gcc \
      gcc-c++ \
      make \
      libgomp \
      mesa-libGL \
      mesa-libEGL \
      libX11 \
      libXext \
      libXrender \
      which && \
    dnf -y clean all && rm -rf /var/cache/dnf

# 기본 python3 symlink -> python3.11 (선택적, 편의용)
RUN ln -sf /usr/bin/python3.11 /usr/bin/python3

# pip 업그레이드(명시적으로 python3.11 실행)
RUN python3.11 -m pip install --upgrade pip setuptools wheel

# 환경변수: paddlex/paddle 캐시를 /tmp로 지정
ENV PADDLE_PDX_CACHE_HOME=/tmp/.paddlex \
    PADDLE_EXTENSION_DIR=/tmp/paddle_extension \
    XDG_CACHE_HOME=/tmp/.cache \
    TMPDIR=/tmp \
    LANG=en_US.utf8

# 파이썬 패키지 설치 (필요한 패키지만)
RUN python3.11 -m pip install \
    numpy==1.26.4 \
    paddlepaddle==3.2.1 \
    paddleocr \
    boto3 \
    supabase \
    opencv-python-headless \
    awslambdaric

# 모델/코드 복사 (모델은 /tmp에 저장)
COPY ocr_models/PP-OCRv5_server_det_infer ocr_models/PP-OCRv5_server_det_infer
COPY ocr_models/korean_PP-OCRv5_mobile_rec_infer ocr_models/korean_PP-OCRv5_mobile_rec_infer
COPY src/services/calc-bill-from-ocr_service.py src/services/calc-bill-from-ocr_service.py
COPY src/utils/supabase_client.py src/utils/supabase_client.py

ENTRYPOINT ["python3.11", "-m", "awslambdaric"]

CMD ["src.services.calc-bill-from-ocr_service.lambda_handler"]