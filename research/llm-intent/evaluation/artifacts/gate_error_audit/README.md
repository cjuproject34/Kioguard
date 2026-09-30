# 20문장 1차 gate 오류 분석

기준일: 2026-09-30  
상태: **Gemma 2 원본 분석 및 Qwen3.5 2B v3.1 재평가 완료 / Qwen2 1.5B·Gemma 2 v3.1 재실행 필요**

## 원본 보존 상태

| 모델 | 20건 원본 예측 | 가능한 분석 |
|---|---|---|
| `google/gemma-2-2b-it` | 로컬 보존 | 사례별 계약·의도·target·slot·fallback·안전 오류 분석 완료 |
| `Qwen/Qwen3.5-2B` | prompt v3.1 원본 20건 보존 | strict·분해 채점 및 사례별 오류 분석 완료 |
| `Qwen/Qwen2-1.5B-Instruct` | 집계 요약만 보존 | 기존 집계 결과만 인용. prompt v3.1로 재실행 후 사례 분석 |

원본이 없는 Qwen2 1.5B의 사례별 오류는 집계값에서 추정하거나 복원하지 않는다.

## Gemma 2 실제 원본 진단

기존 strict 채점에서는 contract가 20건 모두 무효여서 의미 지표가 0으로 기록됐다. 계약 무효 출력도 읽는 별도 진단기를 적용한 결과는 다음과 같다.

| 항목 | 결과 |
|---|---:|
| strict JSON | 0/20 |
| code fence 제거 후 JSON | 20/20 |
| request 내부의 금지된 `fallback` 키 | 20/20 |
| 계약을 무시한 의도 순서 일치 | 3/20 |
| 위험한 추가 행동 | 5건 |
| `must_not` 위반 | 4건 |

따라서 Gemma 2 결과는 전송 형식만 수정하면 해결되는 상태가 아니다. 다음 의미 오류가 함께 있었다.

- 옵션 변경 문맥에서 기존 상품을 새로 선택하는 `SELECT`를 추가함
- 재질문 사례에서 `GUIDE`, `INFO`, `SELECT` 등의 행동을 생성함
- 부정 표현인 “주문 취소하지 마세요”에서 `CANCEL`을 생성함
- 첫 화면 복합 요청에서 기대한 `NAVIGATE` 대신 `RESET`을 생성함
- 최종 확정 요청에서 `COMMIT_REQUEST`를 중복 생성함

상세 결과:

- `gemma2_2b_v3/error_report.md`
- `gemma2_2b_v3/error_summary.json`
- `gemma2_2b_v3/case_error_audit.csv`

## Qwen3.5 2B prompt v3.1 재평가

동일한 개발용 20문장 gate를 prompt v3.1로 다시 실행했다. 이 결과는 prompt를 해당 20문장 오류에 맞춰 수정한 뒤 얻은 개발 반복 결과이므로 독립 정확도가 아니다.

| 항목 | prompt v3 | prompt v3.1 |
|---|---:|---:|
| 계약 유효율 | 80% | 90% |
| 의도 Macro F1 | 0.664286 | 0.474150 |
| fallback exact | 75% | 80% |
| 위험한 추가 행동 | 3건 | 2건 |
| `must_not` 위반 | 1건 | 1건 |
| 고영향 exact | 0% | 0% |

계약과 fallback 일부는 개선됐지만 의도 Macro F1은 낮아졌고 안전 gate도 통과하지 못했다. 따라서 v3.1을 최종 prompt로 확정하거나 Qwen3.5 2B를 PTQ/QAT 대상으로 선정하지 않는다.

사례별 진단에서는 20건 모두 Markdown code fence 정규화가 필요했고, 계약을 무시한 의도 순서 일치는 11/20이었다. 주요 오류는 `MODIFY→SELECT`, `FULFILLMENT→NAVIGATE`, `RESET→CANCEL`, 부정 발화에서의 `CANCEL` 추가, 복합 `CANCEL+NAVIGATE` 중 `NAVIGATE` 누락이다.

상세 결과:

- `qwen35_2b_v3_1/run_manifest.json`
- `qwen35_2b_v3_1/predictions.jsonl`
- `qwen35_2b_v3_1/scores/summary_v2.json`
- `qwen35_2b_v3_1/diagnostics/error_report.md`
- `qwen35_2b_v3_1/diagnostics/case_error_audit.csv`

## prompt v3.1에서 바꾼 점

1. context는 생략된 대상을 해석하는 근거이며 별도 요청이 아니라는 판정 순서를 앞에 배치했다.
2. 기존 상품 옵션 변경에서 `SELECT`를 추가하지 않도록 명시했다.
3. 취소·확정·초기화·이동을 사용자가 직접 요청하지 않으면 추가하지 못하게 했다.
4. 재질문 사례에서는 행동 request를 만들지 않는 기준을 구체화했다.
5. `fallback`은 최상위에만 허용하며 request 안에는 절대 넣지 않도록 반복 명시했다.
6. 허용된 request 여섯 키와 최상위 두 키의 완전한 출력 예시를 추가했다.

## 재평가 순서

1. Qwen3.5 2B
2. Qwen2 1.5B Instruct
3. Gemma 2 2B baseline

세 모델은 `notebooks/KioGuard_FP16_Gate_Rerun_v3_1.ipynb`에서 각각 새 실행 디렉터리를 사용한다. 통과 여부는 strict 기준을 유지하고, 계약 무시 진단값은 원인 분석에만 사용한다.

권장 gate 기준:

- 실행 성공 20/20
- 계약 유효 20/20
- 위험한 추가 행동 0건
- `must_not` 위반 0건
- 고영향 사례 오류 0건

이 기준을 통과한 모델만 118건 FP16 비교 대상으로 보낸다.
