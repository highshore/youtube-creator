# Multi-Agent YouTube Shorts Creator

LangGraph 기반 멀티 에이전트 파이프라인을 FastAPI + Next.js 웹앱으로 리팩터링한 프로젝트입니다.

## 핵심 요구사항 반영

- Python 실행 환경: `uv sync`로 생성되는 `.venv`만 사용
- 버전 관리: `pyproject.toml` 단일 관리
- 모듈러 구조: 노드/서비스/API/UI 분리
- 병렬 처리: 에셋 검색/다운로드를 `ThreadPoolExecutor`로 단일 세션 내부 병렬 수행
- 장애 대응: 오류 triage(일시/치명 구분) + 재시도(backoff) 로직
- 실행 기록: `loguru` 파일/콘솔 로깅 + `tqdm` 진행률 표시

## 디렉터리 구조

```text
.
├── backend
│   └── app
│       ├── main.py
│       ├── job_store.py
│       ├── config.py
│       ├── logging_setup.py
│       ├── models.py
│       └── pipeline
│           ├── graph.py
│           ├── retry.py
│           ├── state.py
│           ├── utils.py
│           └── nodes
│               ├── script_node.py
│               ├── asset_node.py
│               ├── audio_node.py
│               ├── music_node.py
│               ├── assemble_node.py
│               ├── review_node.py
│               └── complete_node.py
├── frontend
│   ├── app
│   ├── components
│   ├── lib
│   └── package.json
├── pyproject.toml
└── .env.example
```

## 1) Python 환경 (venv + uv)

```bash
uv sync
source .venv/bin/activate
```

`uv sync`가 의존성을 `.venv`에 고정 설치합니다.

## 2) 환경 변수

```bash
cp .env.example .env
```

백엔드는 아래 순서로 환경파일을 자동 로드합니다.
- `.env`
- `.env.local`
- `frontend/.env.local`

선택 API 키:
- `OPENAI_API_KEY` (스크립트 생성)
- `PEXELS_API_KEY` (로열티 프리 영상/이미지 검색)
- `ELEVENLABS_API_KEY` (TTS)

키가 없어도 fallback(placeholder/tone)로 파이프라인은 실행됩니다.

## 3) 백엔드 실행 (FastAPI)

```bash
uv run uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

의존성 자동 점검:

```bash
uv run python scripts/check_media_deps.py
```

또는 API로 확인:
- `GET /api/system/dependencies`

## 4) 프론트 실행 (Next.js)

```bash
cd frontend
cp .env.local.example .env.local
npm install
npm run dev
```

브라우저: `http://localhost:3000`

## API 개요

- `POST /api/jobs` : topic으로 생성 시작
- `GET /api/jobs` : 작업 목록
- `GET /api/jobs/{job_id}` : 작업 상세(스크립트/에셋/영상 URL 포함)
- `POST /api/jobs/{job_id}/review` : human review decision 전달 후 resume
- `GET /api/library` : 완료된 스크립트/영상 메타 목록
- `GET /api/system/dependencies` : ffmpeg/ImageMagick 점검 결과
- `GET /media/...` : 생성/다운로드 파일 정적 서빙

## 정책/윤리

- 로열티 프리 또는 라이선스 확보된 에셋만 사용해야 합니다.
- 필요한 경우 출처/저작권 표기를 유지하세요.
- YouTube 정책 준수는 게시 전 최종 검수해야 합니다.
