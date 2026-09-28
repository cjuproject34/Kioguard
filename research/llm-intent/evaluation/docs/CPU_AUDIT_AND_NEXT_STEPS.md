# KioGuard CPU 감사 결과와 다음 실행 순서

기준일: 2026-09-28  
대상: 출력 계약 v3, 선택용 118건, 20문장 gate, 완료된 FP16 네 모델

## 이번에 완료한 작업

원본 JSONL과 기존 채점 결과를 변경하지 않고 CPU 전용 감사 산출물을 만들었다.

- 166건 구조 검증: 오류 0건, 전부 `DRAFT`
- 선택용 118건의 영향도·복잡도·중복 발화·slot·target 조사
- 20문장 gate가 14개 의도 대표 사례와 안전·문맥 사례 6건으로 구성되는지 검증
- 검토용 라우팅 권고: `RULE_CANDIDATE` 45건, `LLM_REQUIRED` 49건, `ROUTER_REVIEW` 24건
- 기존 채점기를 보존하고 세부 오류 지표와 중복 prediction ID 검사를 추가한 v2 채점기 작성
- 기존 네 모델의 Drive 결과를 읽어 의도·target·slots·fallback 오류를 분해
- 원본 prompt와 compact 후보의 정적 크기 비교
- PTQ·QAT 실험 계획 작성

라우팅 권고는 학습 결과가 아니다. 영향도 H, 복잡도 C3/CU, fallback, 복합 요청, 조건 요청을 LLM 필수로 두고, L/M·C1·단일 요청·fallback 없음인 사례만 규칙 후보로 둔 보수적 검토 기준이다.

## 데이터 감사 결과

118건의 영향도는 H 30, M 55, L 26, U 7이고 복잡도는 C1 59, C2 41, C3 17, CU 1이다. 118건 모두 사람이 승인하지 않은 합성 개발 데이터다. 따라서 현재 결과는 모델·프롬프트 개발용 비교에만 사용한다.

같은 발화를 다른 문맥에서 다르게 해석하는 사례가 의도적으로 포함돼 있다. `네` 6건, `카드로 결제할게요` 3건, `아니요` 3건, `아메리카노 한 잔이요` 2건 등이 이에 해당한다. 단순 문자열 중복 제거를 하면 문맥 대조 평가가 사라지므로 삭제하지 않는다.

사람이 우선 검토할 항목은 다음과 같다.

1. 영향도 `U` 7건과 복잡도 `CU` 1건의 기준 확정
2. 요청과 fallback이 함께 있는 조건부 사례 5건의 실행 의미 확정
3. 앱이 실제 지원할 target·slot 표준값 확정
4. 모든 `DRAFT`를 `APPROVED`, `REVISE`, `EXCLUDE`로 판정
5. 모델 선정 뒤 별도 작성자·검수자가 만든 비공개 test 제작

## 20문장 gate 재분석

| 모델 | 계약 유효 | 의도 순서 | target | slots | fallback | 완전 일치 | 위험 추가 행동 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Qwen3.5 0.8B | 0% | 0% | 0% | 0% | 0% | 0% | 0 |
| Qwen3.5 2B | 80% | 45% | 15% | 5% | 75% | 0% | 3 |
| Qwen2 1.5B | 95% | 20% | 15% | 0% | 80% | 0% | 2 |
| Phi-3 Mini | 65% | 45% | 10% | 0% | 55% | 0% | 1 |

이 표는 20건 개발 gate 결과다. 계약 형식 준수와 의미 정확도는 다르다. Qwen2 1.5B는 계약 유효율이 가장 높지만 의도 순서 20%, slots 0%, 위험 추가 행동 2건이어서 주 후보로 채택할 근거가 없다. 완료된 네 모델은 모두 직접 실행 안전 gate를 실패했다.

Colab 생성 시간과 GPU peak는 Android 수치가 아니다. 기존 측정에서 평균 생성 시간은 Qwen2 1.5B 3.57초, Phi-3 Mini 5.09초, Qwen3.5 2B 6.20초, Qwen3.5 0.8B 7.90초였고, GPU peak는 각각 약 3.03, 7.92, 4.26, 1.72 GiB였다.

## prompt 최적화

원본 prompt는 1,873자이고 compact 후보는 1,416자로 24.4% 짧다. 재현 가능한 문자 기반 proxy는 32.7% 감소했다. 이 수치는 모델 tokenizer의 실제 토큰 수가 아니다. GPU가 복구되면 각 모델의 native tokenizer로 실제 입력 토큰을 측정하고, 원본과 compact를 같은 20건에서 A/B 평가해야 한다. compact prompt는 아직 정확도와 안전성을 검증하지 않았으므로 기존 prompt를 대체하지 않는다.

## 다음 실행 순서

1. `router_review_v0.1.csv`와 `gate_review_v0.1.csv`를 사람이 검수한다.
2. GPU가 복구되면 Gemma 4 E2B, Gemma 2 2B, TinyLlama의 20건 gate를 마친다.
3. 일곱 모델 중 안전 gate를 통과한 모델만 118건 selection으로 확장한다.
4. 모두 실패하면 후보를 억지로 정하지 않고 constrained JSON, compact prompt, 소규모 지도 미세조정을 순서대로 비교한다.
5. FP16 후보 1~2개가 확정된 뒤 PTQ Q8_0 → Q6_K → Q5_K_M → Q4_K_M을 지원 범위에서 비교한다.
6. PTQ에서만 생긴 회귀가 확인될 때 QAT 파일럿을 수행한다.
7. 양자화 결과까지는 Colab 기준 연구 결과로 기록하고, Android 수치는 실제 앱 이식 후 별도 측정한다.

## 파일 안내

- `artifacts/cpu_audit/dataset_audit_summary.json`: 분포와 자동 검토 결과
- `artifacts/cpu_audit/router_review_v0.1.csv`: 118건 라우팅 사람 검토표
- `artifacts/cpu_audit/gate_review_v0.1.csv`: 20건 gate 검토표
- `artifacts/cpu_audit/slot_target_inventory.json`: intent별 slot·target 목록
- `artifacts/cpu_audit/existing_gate_error_analysis.json`: 네 모델 오류 분해 요약
- `artifacts/cpu_audit/prompt_size_comparison.json`: prompt 정적 크기 비교
- `scripts/score_predictions_v2.py`: 세부 지표 채점기
- `configs/router_policy_v1.json`: 영향도·복잡도·라우팅 제안
- `docs/PTQ_QAT_EXPERIMENT_PLAN.md`: 양자화 실험 계획

Drive에는 상세 모델별 사례표를 기존 결과와 분리해 `/content/drive/MyDrive/KioGuard/experiments/FP16_COMMON_V3/CPU_ANALYSIS_V1`에 저장했다.
