## 스마트 기숙사 관리 시스템 - API 서버

이 프로젝트는 국민대학교 생활관의 다양한 관리 업무(점호, 상벌점 등)를 자동화하고 효율화하기 위한 **서버리스 API 서버**입니다. 관리자용 웹 대시보드와 학생용 모바일 앱에 필요한 백엔드 기능을 제공합니다.

### 주요 기능

- **호실 및 학생 관리:** 기숙사의 호실, 학생, 관리자 등 핵심 정보를 관리하는 API를 제공합니다.

- **점호 관리:** 근로학생이 모바일/웹을 통해 점호 현황을 기록하고, 관리자가 실시간으로 현황을 파악할 수 있는 기능을 제공합니다.

- **상벌점 관리:** 점호 결과나 기타 사유에 따라 학생에게 상점 및 벌점을 부여하고 이력을 관리합니다.

- **(향후 확장) 택배 관리:** OCR을 활용한 스마트 택배 관리 시스템을 지원합니다.

- **(향후 확장) 문의 및 공지:** 1:1 채팅 문의 및 맞춤형 공지 발송 시스템을 지원합니다.

### 기술 스택

- **언어:** Python 3.11
- **프레임워크:** Serverless Framework v3
- **클라우드:** AWS Lambda, API Gateway (HTTP API)
- **데이터베이스:** PostgreSQL (on Supabase)

### 설치 및 실행

#### 1. 의존성 설치

이 프로젝트는 Node.js(Serverless Framework 플러그인용)와 Python(애플리케이션 코드용) 의존성을 모두 가집니다.

```
# Serverless Framework 플러그인 설치
npm install

# Python 라이브러리 설치
pip install -r requirements.txt
```

#### 2. 환경 변수 설정

프로젝트 루트에 `envs` 폴더를 생성하고, 그 안에 `config.dev.json` 파일을 생성합니다.

**`envs/config.dev.json` 파일 예시:**

```
{
  "SUPABASE_URL": "YOUR_SUPABASE_PROJECT_URL",
  "SUPABASE_API_KEY": "YOUR_SUPABASE_PROJECT_service_role"
}
```

#### 3. 파이썬 포맷팅 설정

설치된 Black 라이브러리를 `src` 디렉토리에 적용하여 코드 파일을 일관적으로 포맷팅합니다.

```bash
python -m black src/
```

### Lambda Layer 빌드(의존성 패키징)

이 프로젝트는 AWS Lambda Layer에 Python 의존성을 포함해 배포합니다. 레이어는 보통 아래 경우에만 다시 빌드합니다.

- `requirements.txt`가 변경되었을 때
- Python 런타임/아키텍처를 변경했을 때(예: 3.11→3.12, x86_64↔arm64)
- 레이어 폴더를 초기화했을 때

#### 빌드 방법

```bash
# 최초 1회(또는 권한 없을 때)
chmod +x build_layer.sh

# 레이어 빌드
./build_layer.sh
```

빌드가 완료되면 아래로 배포합니다.

```bash
sls deploy
```

참고:

- 애플리케이션 코드(`src/**`)만 수정했다면 레이어 재빌드는 필요 없습니다.

### 개발 및 테스트

#### 로컬 서버 실행

Serverless Offline 플러그인을 사용하여 AWS Lambda와 API Gateway 환경을 로컬에서 시뮬레이션할 수 있습니다.

```
# (최초 실행 시 또는 requirements.txt 변경 시) 라이브러리 패키징
sls package

# 로컬 서버 시작
sls offline
```

서버가 성공적으로 실행되면 터미널에 `Server listening on http://localhost:3000` 메시지가 나타납니다.

### 주요 파일 구조

```
src/
├── dto/              # API 데이터 구조(요청/응답) 정의
│   └── base_dto.py
│   └── notice_dto.py
│   └── room_dto.py
│   └── student_dto.py
├── handlers/         # API Gateway 요청을 직접 받는 '팀장' 역할의 파일들
│   └── rooms_handler.py
│   └── notices_handler.py
│   └── students_handler.py
├── services/         # 실제 비즈니스 로직 및 DB 쿼리를 담당하는 '실무자' 역할의 파일들
│   └── rooms_service.py
│   └── notices_service.py
│   └── students_service.py
└── utils/            # DB 연결, 응답 생성 등 공통으로 사용되는 '전문가' 역할의 파일들
    ├── supabase_client.py
    └── responses.py
```
