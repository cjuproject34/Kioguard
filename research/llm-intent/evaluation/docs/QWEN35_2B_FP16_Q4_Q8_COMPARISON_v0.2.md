# Qwen3.5 2B FP16·Q4·Q8 비교 v0.3

작성일: 2026-10-03
대상: Qwen/Qwen3.5-2B revision `15852e8c16360a2fea060d615a32b45270f8a8fc`, prompt v3.1, 공통 gate 20건
유효 실험: `QWEN35_2B_GGUF_CASE_REPLAY_V2`

## 결론

Q8_0은 FP16과 모든 집계 지표 및 사례별 full-exact 판정이 동일했다. FP16 대비 파일은 46.7% 작고 이 CPU 재생 환경에서 평균 생성 시간은 12.3% 짧았다. 동작 보존이 우선이면 Q8_0이 세 형식 중 가장 안전한 선택이다.

Q4_K_M은 FP16보다 66.3% 작고 평균 생성 시간이 30.4% 짧았지만, `CH-CLR-01` 한 건에서 FP16/Q8_0에는 없던 회귀가 발생했다. Macro intent F1도 FP16 대비 0.0786 낮았다. 저장 공간과 CPU 시간이 최우선인 개발용 후보로는 의미가 있으나, 현재 결과만으로 기본 배포 형식으로 확정하기에는 품질 손실이 확인됐다.

세 형식 모두 high-impact full exact가 0%, 위험한 추가 행동 2건, must-not 위반 1건이다. 17/20건이 공통 실패이므로 양자화보다 기본 모델·프롬프트·출력 계약의 정확도 문제가 더 크다. 이 gate만으로 어떤 형식도 프로덕션 준비 완료로 판정하지 않는다.

## 유효성

V1 결과는 품질 비교에서 제외한다. 당시 llama-cli 대화형 배너와 완료되지 않은 thinking trace가 예측으로 채점돼 결과가 오염됐다. V2는 `--single-turn`, `--reasoning-budget 0`, strict JSON 추출·검증을 사용했고 세 형식 모두 20/20 프로세스 성공과 strict JSON 100%를 기록했다.

동일한 모델 revision, prompt hash `69558054aae82c3bd2ad7b613c921ace67697e5898009b8c61292d065b245254`, llama.cpp commit `b04642061d183dff8504127dfbee1c1a8352682c`, seed 20260930, CPU 실행(`-ngl 0`) 조건을 사용했다.

## 집계 비교

| 지표 | FP16 | Q4_K_M | Q8_0 |
|---|---:|---:|---:|
| 파일 크기 | 3.897 GB | 1.312 GB | 2.077 GB |
| FP16 대비 크기 감소 | - | 66.3% | 46.7% |
| 평균 생성 시간/건 | 138.69초 | 96.56초 | 121.63초 |
| FP16 대비 시간 감소 | - | 30.4% | 12.3% |
| strict JSON | 100% | 100% | 100% |
| 계약 유효율 | 80% | 75% | 80% |
| 요청 수 일치율 | 70% | 65% | 70% |
| intent multiset 일치율 | 40% | 30% | 40% |
| target 일치율 | 35% | 30% | 35% |
| slots 일치율 | 20% | 20% | 20% |
| fallback 일치율 | 75% | 70% | 75% |
| 전체 의미 일치율 | 15% | 10% | 15% |
| Macro intent F1 | 0.3908 | 0.3122 | 0.3908 |
| high-impact full exact | 0% | 0% | 0% |
| 위험한 추가 행동 | 2건 | 2건 | 2건 |
| must-not 위반 | 1건 | 1건 | 1건 |

Q8_0은 FP16과 집계값이 완전히 같았다. Q4_K_M은 계약 유효율 -5%p, 요청 수 -5%p, intent 일치율 -10%p, 전체 의미 일치율 -5%p, Macro intent F1 -0.0786을 기록했다.

## 사례별 비교

전체 의미가 완전히 맞은 사례는 FP16과 Q8_0에서 `DEV-NAV-01`, `CH-CLR-01`, `CH-NEG-02` 세 건이고, Q4_K_M에서는 `DEV-NAV-01`, `CH-NEG-02` 두 건이다.

유일한 양자화 전용 회귀는 `CH-CLR-01`이다.

- FP16/Q8_0: `{"requests":[],"fallback":{"type":"ASK_SCREEN_TARGET","field":"screen"}}`
- Q4_K_M: `{"requests":[{"request_id":"r1","intent":"ASK_SCREEN_TARGET",...}],"fallback":{"type":"ASK_SCREEN_TARGET","field":"screen"}}`

Q4_K_M은 fallback으로만 표현해야 할 화면 대상 재질문을 요청 action으로도 추가해 계약 유효성과 전체 의미 일치를 잃었다. Q8_0 전용 회귀나 두 양자화 형식의 회복 사례는 없었다.

공통 실패는 17건이다. 가장 빈번한 불일치 항목은 slots(16건), target(13건), intent multiset/order(각 12건)이다. 이 분포는 현재 병목이 양자화 자체보다 기본 추론 계약과 세부 필드 생성에 있음을 보여준다.

## 선택 기준

- FP16 기준 동작을 최대한 보존하려면 Q8_0을 사용한다.
- 저장 공간과 CPU 처리 시간을 우선하는 실험에서는 Q4_K_M을 사용할 수 있으나 `CH-CLR-01` 회귀를 별도 차단해야 한다.
- QAT는 아직 시작하지 않는다. 먼저 17건의 공통 실패를 줄이고 high-impact gate를 통과시킨 뒤, 동일 V2 하네스로 다시 비교한다.

## 재현 자료

- 집계: `artifacts/ptq_runs/qwen35_2b_gguf_case_replay_v2_aggregate.json`
- 사례별: `artifacts/ptq_runs/qwen35_2b_gguf_case_replay_v2_cases.json`
- 판정: `artifacts/ptq_runs/qwen35_2b_regression_review_v0.1.json`
- 실행 스크립트: `scripts/run_qwen35_2b_gguf_case_replay.py`
- 원본 Drive 실험: `KioGuard/experiments/QWEN35_2B_GGUF_CASE_REPLAY_V2`

생성 시간은 Colab의 동일 CPU 재생 환경에서 비교한 값이며 Android 실기 지연 시간으로 해석하지 않는다.
