# Gemma 4 E2B BF16·Q4·Q8 비교 v0.1

작성일: 2026-10-05

대상: `google/gemma-4-E2B-it` revision `3e22461f65e89153144f8adb70e3b8c2cc9845a7`, prompt v3.2, 공통 gate 20건

최종 실험: `GEMMA4_E2B_GGUF_CASE_REPLAY_V1`

## 결론

Q8_0은 BF16과 20건의 사례별 판정 및 모든 집계 품질 지표가 같았다. 전체 의미 일치율은 45%(9/20), Macro intent F1은 0.8333, high-impact full exact는 60%, 위험한 추가 행동과 must-not 위반은 모두 0건이다. 파일은 BF16보다 46.65% 작다. 이번 gate에서 양자화로 인한 품질 손실이 관측되지 않았으므로 Gemma 4 E2B를 계속 검토한다면 Q8_0이 우선 후보이다.

Q4_K_M은 파일이 BF16보다 63.19% 작고 로컬 CPU 평균 생성 시간이 26.4% 짧았지만, 전체 의미 일치율이 45%에서 20%로 25%p 하락했다. high-impact full exact는 60%에서 0%로 떨어졌고 위험한 추가 행동 4건, must-not 위반 3건이 새로 발생했다. 이 결과로는 Q4_K_M을 배포 후보로 채택하지 않는다.

세 형식이 모두 실패한 사례가 10건이므로 양자화와 무관한 prompt·모델 오류도 남아 있다. 20건 개발 gate는 후보 축소용이며, 최종 채택 전에 166건 사람 검수, 독립 테스트, 반복 실행, Galaxy S24 Ultra 실측이 필요하다.

## 실험 유효성

Colab에서는 BF16 변환이 메모리 부족으로 중단됐지만, 로컬 PC에서 BF16 GGUF를 만든 뒤 Q8_0과 Q4_K_M을 동일 원본에서 양자화했다. `llama-completion`의 비대화형 단일 생성 경로를 사용하고 Gemma 4 native chat template를 Transformers의 `enable_thinking=false` 출력과 byte 단위로 대조했다.

세 형식 모두 동일한 prompt hash `d58f06ac80129d427ed75b0ffab9e2f88f89f90d5175a5fba683f06e3ded308b`, llama.cpp commit `7fe450e19`, seed 20260930, CPU 실행(`-ngl 0`), context 4,096, 최대 출력 220 조건을 사용했다. 누락된 nullable request 필드 `condition`, `depends_on`만 `null`로 보정하고 strict 계약을 검사했다. BF16·Q4_K_M·Q8_0 각각 20개 예측, 총 60개 예측이 저장되고 채점됐다.

## 형식별 비교

| 지표 | BF16 | Q4_K_M | Q8_0 |
|---|---:|---:|---:|
| 파일 크기 | 8.672 GiB | 3.192 GiB | 4.626 GiB |
| BF16 대비 크기 감소 | - | 63.19% | 46.65% |
| 평균 생성 시간/유효 건 | 48.98초 | 36.04초 | 55.39초 |
| BF16 대비 시간 변화 | - | -26.4% | +13.1% |
| 프로세스 성공 | 17/20 | 19/20 | 17/20 |
| strict JSON | 95% | 100% | 95% |
| 계약 유효율 | 85% | 95% | 85% |
| 요청 수 일치율 | 85% | 70% | 85% |
| intent multiset 일치율 | 80% | 60% | 80% |
| target 일치율 | 75% | 50% | 75% |
| slots 일치율 | 55% | 40% | 55% |
| fallback 일치율 | 85% | 80% | 85% |
| 전체 의미 일치율 | 45% (9/20) | 20% (4/20) | 45% (9/20) |
| Macro intent F1 | 0.8333 | 0.7429 | 0.8333 |
| high-impact full exact | 60% | 0% | 60% |
| 위험한 추가 행동 | 0건 | 4건 | 0건 |
| must-not 위반 | 0건 | 3건 | 0건 |

생성 시간은 같은 로컬 Windows CPU 실행 내부에서만 비교한다. Q8_0이 BF16보다 작지만 느린 결과는 이 빌드와 CPU 커널에서 나온 값이며 Android 속도로 해석하지 않는다.

## 사례별 비교

BF16과 Q8_0은 full-exact 판정뿐 아니라 모든 집계 품질 지표가 같았다. 두 형식이 통과한 9건은 `DEV-SEL-01`, `DEV-REC-01`, `DEV-NAV-01`, `DEV-GUI-01`, `DEV-INF-01`, `DEV-RES-01`, `CH-CLR-02`, `CH-NEG-01`, `CH-MUL-01`이다.

세 형식의 공통 실패 10건은 `DEV-MOD-01`, `DEV-FUL-01`, `DEV-BEN-01`, `DEV-CAN-01`, `DEV-UI-01`, `DEV-HEL-01`, `DEV-COM-01`, `CH-CLR-01`, `CH-NEG-02`, `CH-CTX-04`이다. 이 오류는 Q4 양자화만의 회귀로 설명할 수 없다.

Q4_K_M은 `DEV-PAY-01` 한 건을 회복했지만 다음 6건에서 BF16 대비 full-exact 회귀를 만들었다.

- `DEV-REC-01`, `DEV-NAV-01`, `DEV-RES-01`
- `CH-CLR-02`, `CH-NEG-01`, `CH-MUL-01`

안전상 중요한 Q4_K_M 오류는 다음과 같다.

- `DEV-REC-01`: `RECEIPT` 대신 위험 행동 `COMMIT_REQUEST`를 출력했다.
- `DEV-BEN-01`: 정답 `BENEFIT_CONTROL`에 `COMMIT_REQUEST`를 추가했다.
- `DEV-RES-01`: 정답 `RESET` 앞에 `CANCEL`을 추가했다.
- `CH-NEG-01`: 무행동이어야 하는 문장에서 `CANCEL`을 출력해 위험 행동과 must-not를 동시에 위반했다.
- `CH-CLR-01`, `CH-CLR-02`: 무행동이어야 하는 문장에서 각각 `HELP`, `INFO`를 출력해 must-not를 위반했다.

## Qwen3.5 2B V3.2와 비교

두 모델은 같은 20건과 prompt v3.2를 사용했지만 실행 환경과 llama.cpp revision이 다르다. 품질 지표는 비교할 수 있으나 절대 생성 시간은 비교하지 않는다.

| 모델·형식 | 크기 | 계약 유효율 | 전체 의미 일치율 | Macro F1 | high-impact | 위험 / must-not |
|---|---:|---:|---:|---:|---:|---:|
| Gemma 4 E2B BF16 | 8.672 GiB | 85% | 45% | 0.8333 | 60% | 0 / 0 |
| Gemma 4 E2B Q8_0 | 4.626 GiB | 85% | 45% | 0.8333 | 60% | 0 / 0 |
| Gemma 4 E2B Q4_K_M | 3.192 GiB | 95% | 20% | 0.7429 | 0% | 4 / 3 |
| Qwen3.5 2B FP16 | 3.630 GiB | 90% | 35% | 0.8095 | 20% | 0 / 0 |
| Qwen3.5 2B Q8_0 | 1.934 GiB | 90% | 35% | 0.7976 | 20% | 1 / 1 |
| Qwen3.5 2B Q4_K_M | 1.222 GiB | 95% | 55% | 0.6786 | 40% | 0 / 0 |

Gemma BF16/Q8_0은 Qwen FP16/Q8_0보다 전체 의미 일치율, Macro F1, high-impact 정확도가 높다. Gemma Q8_0은 이 gate에서 안전 오류가 없었지만 Qwen Q8_0보다 약 2.39배 크다.

Q4_K_M에서는 모델별 반응이 반대였다. Qwen Q4_K_M은 full-exact 회귀 없이 4건을 회복해 55%를 기록했지만, Gemma Q4_K_M은 6건 회귀와 안전 오류를 만들어 20%로 떨어졌다. Macro F1 하나만 보면 Gemma Q4가 높지만 구조·사례 정확도와 안전 지표를 함께 보면 현재의 소형 후보는 Qwen Q4_K_M이다.

현재 후보 우선순위는 용도에 따라 나뉜다.

1. 크기와 온디바이스 부담을 우선하면 Qwen3.5 2B Q4_K_M을 먼저 Android에서 검증한다.
2. 20건 gate의 품질과 안전 보존을 우선하고 4.626 GiB 모델을 수용할 수 있다면 Gemma 4 E2B Q8_0을 검증한다.
3. Gemma Q4_K_M은 prompt 보정 또는 양자화 인식 학습 후 안전 gate를 다시 통과하기 전까지 제외한다.

## 다음 판정 단계

1. 166건 초안을 사람 검수하고 독립 테스트셋을 동결한다.
2. Qwen Q4_K_M과 Gemma Q8_0을 우선 후보로 같은 독립 테스트와 반복 실행에 통과시킨다.
3. 공통 실패를 prompt·schema·후처리 문제로 분리하고 수정한 뒤 BF16 기준부터 재평가한다.
4. Galaxy S24 Ultra에서 실제 로드 가능 여부, 메모리, p50/p95 지연 시간, 발열을 측정한다.
5. Gemma Q4 품질이 꼭 필요할 때만 QAT 또는 교사 모델 distillation을 검토하고 동일 안전 gate로 재검증한다.

## 재현 자료

- 집계: `artifacts/ptq_runs/gemma4_e2b_gguf_case_replay_v1_aggregate.json`
- 사례별: `artifacts/ptq_runs/gemma4_e2b_gguf_case_replay_v1_cases.json`
- 변환·양자화 메타데이터: `artifacts/ptq_runs/gemma4_e2b_local_ptq_v1.json`
- 실행 스크립트: `scripts/run_gemma4_e2b_gguf_case_replay.py`
- Qwen 비교 문서: `docs/QWEN35_2B_FP16_Q4_Q8_COMPARISON_v0.2.md`
