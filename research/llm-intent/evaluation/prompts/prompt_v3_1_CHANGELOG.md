# prompt v3.1 변경 기록

prompt v3.1은 20문장 1차 gate의 오류를 줄이기 위한 재평가용 프롬프트다. prompt v3 원문과 결과는 baseline으로 그대로 보존한다.

## 변경 근거

- Gemma 2가 모든 request에 계약에 없는 `fallback` 키를 추가했다.
- context의 선택 상품과 available action을 사용자 요청으로 오인해 요청 수를 늘렸다.
- 부정·재질문·첫 화면 이동 사례에서 위험 행동이나 불필요한 행동을 생성했다.

## 변경 범위

- intent 목록, 정규화 enum, JSON의 의미 계약은 v3과 동일하다.
- 판정 순서와 금지 규칙을 앞부분으로 이동했다.
- request 수준의 `fallback` 금지를 명시했다.
- `NAVIGATE`와 `CANCEL`·`RESET`, `PAYMENT_METHOD`와 `COMMIT_REQUEST`, `MODIFY`와 `SELECT`의 경계를 보강했다.
- 정상 행동 출력과 fallback-only 출력 예시를 각각 하나 추가했다.

## 해석 제한

v3.1의 20문장 결과는 같은 사례를 보고 수정한 개발 결과다. v3보다 개선돼도 독립 test 정확도로 보고하지 않는다. 118건 역시 모델·프롬프트 선정용 개발 데이터이며 최종 후보에는 별도 비공개 test가 필요하다.
