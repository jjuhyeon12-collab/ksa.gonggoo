# GongGoo Backend (Django)

## 빠른 시작

```bash
# 1. 가상환경 생성 & 의존성 설치
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt

# 2. 환경변수 설정
copy .env.example .env       # 값 수정 후 저장

# 3. DB 마이그레이션
python manage.py migrate

# 4. 관리자 계정 생성
python manage.py createsuperuser

# 5. 서버 실행 (WebSocket 포함 — daphne 사용)
daphne -b 0.0.0.0 -p 8000 gonggoo.asgi:application

# 개발용 간단 실행 (WebSocket 불필요 시)
python manage.py runserver
```

## API 엔드포인트

### 인증 (`/api/auth/`)
| Method | URL | 설명 |
|--------|-----|------|
| POST | `/api/auth/register/` | 회원가입 (학교 이메일 전용) |
| POST | `/api/auth/login/` | 로그인 → JWT 발급 |
| POST | `/api/auth/token/refresh/` | 액세스 토큰 갱신 |
| GET/PATCH | `/api/auth/me/` | 내 정보 조회/수정 |

### 공동구매 (`/api/buys/`)
| Method | URL | 설명 |
|--------|-----|------|
| GET | `/api/buys/` | 목록 조회 (검색/필터/정렬) |
| POST | `/api/buys/` | 공동구매 개설 |
| GET | `/api/buys/<id>/` | 상세 조회 |
| PATCH | `/api/buys/<id>/` | 수정 (개설자만) |
| DELETE | `/api/buys/<id>/` | 삭제 (개설자만) |
| POST | `/api/buys/<id>/join/` | 참여 |
| DELETE | `/api/buys/<id>/leave/` | 참여 취소 |
| GET | `/api/buys/mine/` | 내가 개설/참여한 목록 |

### 검색 & 필터 쿼리 파라미터
```
GET /api/buys/?search=에어팟          # 제목·설명 키워드 검색
GET /api/buys/?status=open            # 상태 필터 (open/matched/cancelled/expired)
GET /api/buys/?buy_type=bundle        # 방식 필터 (bundle/min_order)
GET /api/buys/?min_price=5000         # 최저 가격
GET /api/buys/?max_price=30000        # 최고 가격
GET /api/buys/?ordering=-unit_price   # 정렬 (-created_at, deadline, unit_price)
```

### WebSocket
```
ws://localhost:8000/ws/buys/<id>/
```
연결 시 즉시 현재 인원 수 전송, 참여/취소 시 실시간 브로드캐스트.

## 공동구매 방식

| 방식 | `buy_type` | 필수 필드 | 매칭 조건 |
|------|-----------|----------|---------|
| 묶음 나눠사기 | `bundle` | `total_count` | 참여 수량 합계 == total_count (초과 불가) |
| 최소주문금액 | `min_order` | `target_amount` | 참여 수량 × 단가 >= target_amount |

## 관리자 페이지
`http://localhost:8000/admin/`
