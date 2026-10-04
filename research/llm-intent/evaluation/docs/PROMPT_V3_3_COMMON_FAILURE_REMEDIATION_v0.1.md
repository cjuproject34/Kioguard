# prompt v3.3 공통 실패 개선 계획 v0.1

작성일: 2026-10-05

## 분석 범위

Qwen3.5 2B V3.2의 FP16·Q4_K_M·Q8_0 공통 실패 9건과 Gemma 4 E2B V1의 BF16·Q4_K_M·Q8_0 공통 실패 10건을 비교했다. 두 모델군이 함께 실패한 사례는 다음 6건이다.

- `DEV-FUL-01`, `DEV-BEN-01`, `DEV-CAN-01`
- `DEV-UI-01`, `DEV-HEL-01`, `DEV-COM-01`

동일 20건을 보고 prompt를 수정했으므로 이후의 20건 점수는 개발 회귀 확인에만 사용한다.

## 원인 분류

| 원인 | 대표 사례 | 관찰된 문제 | v3.3 변경 |
|---|---|---|---|
| 값 없는 slot 추가 | DEV-FUL-01, DEV-BEN-01, DEV-UI-01, DEV-COM-01 | `null`, `confirmation`, `degree` 등 발화에 없는 값을 추가 | 확인된 값만 slots에 기록하고 null slot 금지 |
| target 정규화 오류 | DEV-NAV-01, DEV-HEL-01, CH-NEG-02, CH-MUL-01 | 목적지를 target으로 사용하거나 일반 도움 target을 잘못 선택 | NAVIGATE=`APP_UI`, 일반 HELP=`CURRENT_TASK` 규칙 추가 |
| intent 경계 오류 | DEV-CAN-01, DEV-RES-01 | 항목 제거를 MODIFY로 처리하거나 RESET을 CANCEL+NAVIGATE로 과분해 | 항목 제거=CANCEL, 전체 초기화=RESET 하나로 명시 |
| fallback·부정·계약 | DEV-MOD-01, CH-CLR-01, CH-CLR-02, CH-NEG-01 | fallback 키 누락, 모호성을 HELP/INFO로 실행, 부정 행동 실행 | 계약 완전성, 모호성 fallback, 부정 우선 규칙 강화 |
| 확인값 매핑 | CH-CTX-04 | `ACCEPT`를 action으로 사용 | action=`proposed_value`, confirmation=`ACCEPT`로 분리 |

## 승격 조건

Gemma BF16 v3.3 20건 회귀가 다음 조건을 모두 만족할 때만 166건 개발 평가로 이동한다.

- 위험한 추가 행동 0건
- must-not 위반 0건
- high-impact full exact 60% 이상
- 계약 유효율 85% 이상

전체 의미 일치율과 Macro F1은 개선 여부를 기록하지만 안전 gate보다 먼저 사용하지 않는다.

## 확장 평가 범위

승격 후 `selection_dev_v0.1` 84건, `selection_challenge_v0.1` 34건, `legacy48_regression_v1.2` 48건을 합쳐 총 166건을 실행한다. 전부 `DRAFT`이므로 이 결과는 개발 평가이며 최종 일반화 정확도가 아니다.

독립 테스트셋은 prompt v3.3과 166건 결과를 보지 않은 별도 작성·검수 절차로 만들어야 한다. 현재 단계에서는 실행기와 판정 기준만 준비하고 독립 점수라고 표기하지 않는다.

## 20건 BF16 회귀 결과

실험 `GEMMA4_E2B_BF16_PROMPT_V3_3_GATE_V1`은 20건 생성과 채점을 완료했다. 최초 실행에서 17건이 계약 유효였고, 의미 추론 없이 누락된 최상위 nullable `fallback`만 `null`로 보정한 뒤 `DEV-MOD-01`이 회복되어 최종 계약 유효 출력은 18/20이 됐다.

| 지표 | v3.2 | v3.3 | 변화 |
|---|---:|---:|---:|
| strict JSON | 95% | 90% | -5%p |
| 계약 유효율 | 85% | 90% | +5%p |
| intent multiset 일치 | 80% | 85% | +5%p |
| target 일치 | 75% | 90% | +15%p |
| slots 일치 | 55% | 75% | +20%p |
| 전체 의미 일치 | 45% (9/20) | 75% (15/20) | +30%p |
| Macro intent F1 | 0.8333 | 0.8810 | +0.0476 |
| high-impact full exact | 60% | 100% | +40%p |
| 위험한 추가 행동 | 0건 | 0건 | 유지 |
| must-not 위반 | 0건 | 0건 | 유지 |

v3.2에서 실패했던 6건이 회복됐고 기존 정답 사례의 회귀는 없었다.

- 회복: `DEV-MOD-01`, `DEV-PAY-01`, `DEV-HEL-01`, `DEV-COM-01`, `CH-NEG-02`, `CH-CTX-04`
- 회귀: 없음

prompt는 Gemma 4 토크나이저 기준 2,407토큰에서 3,027토큰으로 증가했다. 유효 출력의 평균 생성 시간도 48.98초에서 66.17초로 약 35.1% 늘었다. 품질 향상과 함께 생긴 비용이며, 확장 전에 prompt 축약을 검토할 근거다.

## 잔여 실패 5건

| 사례 | 잔여 문제 | 판정 |
|---|---|---|
| `DEV-FUL-01` | 매장 이용 발화를 `TAKEOUT`으로 분류 | 의미 정규화 오류 |
| `DEV-BEN-01` | target과 중복되는 `benefit` slot 추가 | 과잉 slot |
| `DEV-CAN-01` | 주문 항목 제거를 여전히 MODIFY로 분류 | intent 경계 오류 |
| `DEV-UI-01` | 의도 자체는 UI_CONTROL 방향이나 JSON 배열·request 구조가 깨짐 | 구조화 출력 오류 |
| `CH-CLR-01` | ASK_SCREEN_TARGET 대신 HELP를 시도하고 JSON 구조도 깨짐 | fallback 경계·구조 오류 |

v3.3은 사전 정의한 승격 조건을 모두 충족했지만, 사용자 결정에 따라 이번 작업은 20건 공통 실패 개선까지만 마치고 166건 평가는 실행하지 않는다.

## 재현 자료

- 최종 집계: `artifacts/ptq_runs/gemma4_e2b_bf16_prompt_v3_3_gate_v1_aggregate.json`
- v3.2 대비 사례별 변화: `artifacts/ptq_runs/gemma4_e2b_bf16_prompt_v3_3_gate_v1.json`
- 공통 실패 분류: `artifacts/gate_error_audit/prompt_v3_3_common_failure_plan.json`
- prompt: `prompts/prompt_v3_3_full.txt`
