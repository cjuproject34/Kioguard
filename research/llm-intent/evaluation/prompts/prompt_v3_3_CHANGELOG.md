# prompt v3.3 변경 기록

작성일: 2026-10-05

## 목적

Gemma 4 E2B와 Qwen3.5 2B의 prompt v3.2 20건 개발 gate에서 반복된 공통 오류를 줄인다. 동일한 20건을 보고 수정했으므로 v3.3의 해당 gate 결과는 개발 회귀 결과이며 독립 정확도로 사용하지 않는다.

## 변경 사항

- 최상위 `requests`, `fallback`과 request의 여섯 키를 항상 출력하도록 명시했다.
- 값이 없거나 발화에서 확인되지 않은 slot과 `null` slot을 금지했다.
- 직접 명령에는 `confirmation`을 추가하지 않고 확인 대화의 명시적 수락에만 사용하도록 경계를 정했다.
- 주문 항목 제거는 `CANCEL`, 속성 변경은 `MODIFY`로 구분했다.
- 결제수단·영수증·혜택 선택에 `COMMIT_REQUEST`를 추가하지 않도록 했다.
- 전체 초기화는 `RESET` 하나로 처리하고 `CANCEL`·`NAVIGATE`를 중복 생성하지 않도록 했다.
- `NAVIGATE` target을 `APP_UI`로 고정하고 화면 목적지는 `slots.destination`에 두도록 했다.
- 일반 도움, 사람 도움, 화면·장치 문제의 HELP target 경계를 명시했다.
- 모호한 화면 찾기와 안내 필요 여부는 각각 `ASK_SCREEN_TARGET`, `ASK_GUIDANCE_NEED`로 처리하도록 했다.
- `CONFIRM_COMMIT` 수락 시 action에는 `proposed_value`, confirmation에는 `ACCEPT`를 사용하도록 했다.
- 의미 추론 없이 최상위 nullable `fallback`만 빠진 JSON은 `fallback:null`로 보정하도록 실행기를 확장했다. 괄호, intent, target, slots는 복원하지 않는다.

## 평가 원칙

1. 먼저 기존 20건 BF16 회귀를 실행한다.
2. 위험 행동 또는 must-not 위반이 증가하면 확장 평가로 이동하지 않는다.
3. 통과하면 현재 `DRAFT` 상태의 selection 118건과 legacy 48건을 개발 평가로 실행한다.
4. 최종 채택 점수는 별도 작성·검수된 독립 테스트셋에서 산출한다.

## 20건 회귀 결과

- 전체 의미 일치: 45% → 75%
- Macro intent F1: 0.8333 → 0.8810
- high-impact full exact: 60% → 100%
- 위험한 추가 행동 / must-not 위반: 0/0 → 0/0
- 회복 6건, 회귀 0건
- 잔여 실패 5건

strict JSON은 95%에서 90%로 낮아졌지만 nullable `fallback` 보정 후 계약 유효율은 85%에서 90%로 높아졌다. 이 결과는 prompt 수정에 사용한 같은 20건의 개발 회귀 결과다.
