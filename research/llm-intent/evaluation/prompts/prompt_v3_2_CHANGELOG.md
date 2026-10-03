# prompt v3.2 변경 기록

prompt v3.2는 동일 CPU·llama.cpp 조건의 Qwen3.5-2B GGUF V2 사례별 결과에서 확인된 17건의 공통 실패를 줄이기 위한 개발 프롬프트다. v3.1과 V2 결과는 비교 기준으로 보존한다.

## 변경 근거

- 모델이 `ASK_SCREEN_TARGET`과 같은 fallback type을 request intent로 사용했다.
- intent는 맞아도 화면 이름을 target으로 복사하거나 임의의 slot 키를 생성했다.
- 부정된 CANCEL을 실행하고, 두 단계 요청을 한 request로 축소했다.
- `COMMIT_REQUEST`를 허용되지 않은 `COMMIT` intent로 출력했다.
- 사실 질문, 안내, 도움, 초기화와 같은 intent 경계를 반복해서 혼동했다.

## 변경 범위

- fallback type을 request intent로 사용할 수 없다는 절대 규칙을 맨 앞에 배치했다.
- 부정 범위, 독립 행동 수, 직전 확인 질문을 intent 선택보다 먼저 처리하도록 판정 순서를 바꿨다.
- 14개 intent별 target 규칙과 허용 slot 키를 명시했다.
- context ID, 정규화 target, 화면 이름 사이의 우선순위를 명시했다.
- SELECT/MODIFY, INFO/NAVIGATE, GUIDE/fallback, CANCEL/RESET, COMMIT_REQUEST와 부정문에 대한 대비 예제를 추가했다.

## 평가 제한

이 프롬프트는 기존 20건 gate의 오류를 보고 작성한 개발 결과다. 같은 20건에서 개선돼도 독립 test 정확도로 간주하지 않는다. gate 통과 후 전체 selection·legacy 회귀와 별도 비공개 test가 필요하다.
