# KioGuard 기존 Colab 실험 검토보고서


## 1. 판단

기존 실험에는 재사용할 수 있는 결과와 실제 문제해결 기록이 있다. 그러나 독립 평가 데이터에 대한 일반화 성능, 동일 조건의 양자화 무손실, 모바일 자원 효율을 확정하는 근거로는 부족하다. 특히 평가 예시의 프롬프트 포함, 실험 설정 차이, 일부 결과의 원출력 부재, 학습 데이터 수 불일치를 수정해야 한다.

모든 성능 실험은 사용자 확인에 따라 **Colab 실험**으로 분류한다. 이번 검토에서 모델을 재추론하거나 Colab 셀을 실행하지 않았다. Drive 원본도 수정하지 않았다. 내려받아 읽은 코드에서 외부 실행·모델 로딩과 무관한 Rule/Parser 함수만 분리하여 로컬에서 검산했고, 저장된 Q4 예측으로 Hybrid 결과를 재구성했다. 이 검산은 모델 성능 재실험이 아니다.

## 2. 검토 범위와 근거

| 자료 | 확인 범위 |
|---|---|
| [Kioguard_LLM_의도분석.ipynb](https://colab.research.google.com/drive/1qBzq4hSVDS4_nA4QeI8_qVWLpzYvW1rC) | 54개 셀의 코드·저장 출력. 초기 후보 비교, 변환, PTQ, 초기 파싱 |
| [양자화재측정.ipynb](https://colab.research.google.com/drive/1B0-5SiSmxf4AGDcpbRJy-saVNDT2U6Rf) | 14개 셀. Q8 재측정, GGUF metadata, 환경 복원 |
| [재시작.ipynb](https://colab.research.google.com/drive/1AEyW24UrRKKFjwF52f9SJJ05Bt0EN7Ba) | 19개 셀. template·별칭 교정, Q4 최종 48건, f16 최종 48건 |
| [안C 경량분류기.ipynb](https://colab.research.google.com/drive/1Ru8wvzSKufuDJ8ib_ZG1U4J5JuoIjn6s) | 7개 셀. 학습 데이터 로딩, centroid·로지스틱 회귀 |
| [kioguard_llm_core.py](https://drive.google.com/file/d/1MsuWZ-t5fA90FJ5q5qW1uTmXjfwt5GNl/view) | Rule, Hybrid, prompt, parser, CLI 호출 |
| [llm_intent_eval.py](https://drive.google.com/file/d/1rZLU9HF74xF599oBzvjZDmnRie4T0Dzi/view) | CSV 로딩, 정확도 산식, timing, 기본 parser |
| [LLM_정답라벨_48.csv](https://drive.google.com/file/d/1N10Qfh3NN_WVdxdqVGXyw1ePFQ08kcLz/view) | 전체 48행, 중복·분포·Rule 검산 |
| [LLM_학습데이터_QAT.csv](https://drive.google.com/file/d/1Fna6PuRV6jEDqoBxBTQs1_SclbDAaswA/view) | 전체 126행, 분포, 테스트 문자열 중복 검사 |
| [STT_TTS_LLM_260822.ipynb](https://colab.research.google.com/drive/1ayw4qiTgsnCMaWkqjnNGD3FJr9y9DwFo) | 통합 경로 코드와 샘플 저장 출력 |
| [PC버전.ipynb](https://colab.research.google.com/drive/1djn6y5-hR5Kj1MDdzx1WnsWgEOKheWcw) | 9개 셀의 실행 경로·샘플 진단 확인 |
| [LLM_어려웠던점_해결과정.md](https://drive.google.com/file/d/1-VdH29u3BYDNb_RAigvuFWB5sonY7-yj/view) | 설명·결론과 노트북 근거 대조 |

앞서 읽은 로컬 엑셀의 보고값도 대조했다. Drive 엑셀과 로컬 엑셀을 동일 버전이라고 가정하지 않았다. 셀 번호는 현재 저장된 노트북의 위에서부터 순서이며 execution_count와 다르다. 일부 초기 셀의 execution_count는 null이다.

## 3. 결과별 판정

| 보고 항목 | 확인한 근거 | 판정 |
|---|---|---|
| Rule 93.8% | 제공된 Rule 함수와 현재 정답 CSV로 45/48 재계산 | **수치 재현.** 기존 개발셋 성능으로 보존 |
| Qwen2 41.7/52.1/62.5% | 메인 노트북 셀 4/6/7에 20/25/30건 정답 기록 | **저장 결과 확인.** 튜닝 경과이며 독립 test 성능 아님 |
| Gemma Transformers 85.4%, 465ms | 엑셀·문서에는 있으나 메인 측정 셀 10의 저장 출력은 NameError | **원출력 미확인.** 과거 실행이 없었다는 뜻은 아니지만 검토 범위에서 검증 불가 |
| Phi-3-mini 79.2%, 1238ms | 메인 셀 14에 38/48 및 지연 기록 | **저장 결과 확인.** 해당 prompt·runtime 조건으로 한정 |
| TinyLlama 0%, 843ms | 메인 셀 16에 0/48, 영어 설명 출력·미분류 기록 | **해당 출력 계약 실패 기록으로 보존.** 일반 능력 0%·모델 붕괴로 일반화 금지 |
| Gemma Q4 최종 85.4% | 재시작 셀 15에서 48건 라벨과 41/48 확인 | **저장 결과 확인.** 개별 raw 생성문은 전부 저장돼 있지 않아 독립 재채점은 제한 |
| Gemma Q8 교정 후 85.4% | 교정 전 33/48 기록은 있으나 최종 template+별칭 조건의 전체 출력 미확인 | **최종값 검증 보류.** 최종 조건 재측정 필요 |
| f16 GGUF 교정 후 85%대 | 재시작 셀 18은 37/48=77.1%. 셀 19는 GV-01의 raw 진단만 존재 | **85%대는 미확인.** 수정 후 전체 재측정 기록 필요 |
| Hybrid 97.9%, 2/48 호출 | 현재 Rule+저장된 Q4 예측을 조합하면 47/48, 2/48로 재구성 | **재구성 확인.** 엑셀에 적힌 원본 모델 Hybrid 실험 자체의 재현은 아님 |
| 애매한 경우도 LLM 89.6%, 15/48 호출 | 같은 재구성에서 43/48, 15/48 | **재구성 확인.** 새 분포에서 같은 정책 우위를 보장하지 않음 |
| 임베딩 centroid 87.5% / 회귀 89.6% | 경량분류기 셀 5/7에 42/48, 43/48 | **저장 결과 확인.** 해당 실행의 학습 데이터는 126개 |
| FP16→Q8→Q4 크기 감소 | 변환·양자화 로그와 파일 목록 확인 | **압축 성과 유지 가능.** GB/GiB 정리, RAM과 분리 필요 |
| QAT로 성능 회복 | 검토한 노트북에 QAT 학습·변환·전후 평가 기록 없음 | **성과로 기재 불가.** 학습용 CSV 존재는 QAT 수행 근거가 아님 |

## 4. 우선 수정할 문제

### A. 평가 문장과 정답이 prompt 예시에 직접 들어 있음 — 중요도 최상

메인 노트북 셀 6의 few-shot 예시는 테스트 6행과 문자열이 같다. `아이스로 바꿔주세요`(FD-04), `여기서 먹고 갈게요`(FD-07), `카드로 결제할게요`(FD-14/GV-11), `처음으로 돌아가주세요`(FD-22/GV-19)다.

셀 7 및 셀 11의 개선 prompt에도 테스트 5행이 포함된다. `영수증 필요해요`(FD-17/GV-14), `어르신 할인 되나요`(GV-15), `뒤로 가고 싶어요`(FD-21/GV-18)와 정답 라벨이 예시로 제시된다. [셀 7](https://colab.research.google.com/drive/1qBzq4hSVDS4_nA4QeI8_qVWLpzYvW1rC#scrollTo=089icPiKht-E)

따라서 해당 결과는 정답을 보지 않은 새 문장에 대한 독립 평가가 아니다. 평가 오답을 보고 prompt·parser를 반복 수정한 점도 추가로 개발셋 성격을 만든다. 반면 최종 Q4 prompt에는 위의 five-shot 블록이 없다. 오염 경로가 모든 실행에서 동일하다고 주장하지 않는다.

조치: 48건을 V1 개발/회귀셋으로 고정한다. 새 test는 Rule·예시·parser·모델 선택에 사용하지 않는다. few-shot은 별도의 train/dev에서만 선정한다. 기존 수치를 삭제하거나 새 test와 합치지 않는다.

### B. “양자화 무손실”은 현재 비교로 확정할 수 없음 — 중요도 최상

원본 Transformers와 Q4 측정은 정밀도 외에도 바뀐 것이 많다.

| 비교 항목 | Transformers 경로 | 최종 Q4 경로 |
|---|---|---|
| prompt | 분류 정의+5개 예시+추가 지시 | 분류 정의 중심, 위 예시 없음 |
| 최대 생성량 | 16 tokens | CLI -n 8 |
| parser | 전체 생성문에서 정식 라벨·일부 별칭 탐색 | CLI 통계 앞 마지막 비어 있지 않은 줄에서 별칭 탐색 |
| runtime/backend | Transformers, device_map=auto | llama.cpp, -ngl 0, 저장 빌드는 CPU 경로 |
| 실행 수명 | 로드된 모델 재사용 | 발화마다 새 CLI 프로세스 및 모델 로딩 |

같은 llama.cpp 경로의 f16은 실제 저장값이 77.1%(37/48)이고 Q4는 85.4%(41/48)다. f16의 미분류 4행을 parser로 구제할 수 있다는 가설은 있으나, raw 진단은 GV-01 한 건이고 수정 후 전체 결과가 없다. f16과 Q4는 FD-06, FD-19, GV-01~04 등 6행에서 예측이 다르다. 총 정확도가 나중에 같아져도 사례별 출력이 같다는 뜻은 아니다. [f16 측정 셀](https://colab.research.google.com/drive/1AEyW24UrRKKFjwF52f9SJJ05Bt0EN7Ba#scrollTo=R7EPL7Q90MOL)

보존할 결론: “입력 형식과 parser 교정 후 Q4의 관측 정확도가 85.4%로 회복되었다.” 보류할 결론: “FP16/Q8/Q4의 양자화 손실이 모두 0이다.” Q8이 항상 무손실이어야 한다거나, 양자화 모델이 비양자화 모델보다 높게 나오면 반드시 버그라는 전제도 두지 않는다.

조치: 같은 원본 revision, runtime, prompt, tokenizer 경로, 출력 길이, parser로 f16/Q8/Q4를 비교한다. raw 출력과 모델 파일 hash를 저장한다. 모델·변환 도구 revision 미고정 상태의 재다운로드는 정확한 동일 원본 재현으로 부르지 않는다.

### C. Hybrid 개선은 같은 문장 두 행에서 발생 — 중요도 최상

Rule 검산 결과는 45/48이며 오답은 FD-11(`아이스 아메리카노 디카페인`→옵션변경), GV-01/GV-03(`민원서류 떼러왔어요`→미분류)이다. no_match는 GV-01/GV-03 두 행뿐이고 문장은 완전히 동일하다.

Q4 저장 예측은 이 두 행을 주문으로 맞힌다. 따라서 Rule+Q4 예측 재구성은 47/48=97.9167%, 호출 2/48=4.1667%가 된다. 애매한 경우도 보내면 43/48=89.5833%, 호출 15/48=31.25%로 재구성된다. 이 값들은 새 LLM 추론을 수행한 결과가 아니다.

개선 기여를 보여주는 서로 다른 발화는 한 종류다. 그러므로 “Rule의 빈틈을 LLM이 보완한 사례”는 유지할 수 있지만 “실사용 발화의 96%를 안정적으로 Rule이 처리한다”거나 “no_match_only가 일반적으로 최선이다”는 결론은 보류한다. 현재 48행 중 문자열 고유값은 38종, 공백·문장부호를 제거하면 37종이다. 도메인별 같은 문장을 두는 것 자체가 잘못은 아니지만 문장 다양성과 행 수는 구분해야 한다.

### D. 247개 학습 데이터라는 설명이 실제 파일·출력과 다름 — 중요도 높음

현재 Drive의 학습 CSV는 126행이다. 경량분류기 셀 3의 실행 출력도 `학습 126개, 테스트 48개`다. 주석과 엑셀의 247개 설명과 다르다. [학습 로딩 셀](https://colab.research.google.com/drive/1Ru8wvzSKufuDJ8ib_ZG1U4J5JuoIjn6s#scrollTo=338vMzDWsZ_6)

126개의 분포: 주문 28, 옵션변경 20, 매장/포장 12, 결제 14, 할인/쿠폰 12, 취소/처음으로 12, 도움요청 16, 정보문의 12. 현재 train/test의 완전 동일 문장 및 공백·문장부호 제거 후 동일 문장은 0건이다. 이 부분은 확인 가능하다. 다만 이것이 의미상 유사 문장이나 개발 과정의 간접 누수가 없다는 보장은 아니다.

조치: 87.5%/89.6%를 설명할 때 현재 확인 가능한 학습 수는 126개로 표기한다. 별도 247개 버전이 있었다면 파일·hash·실행 결과로 연결한다. centroid 방식은 “추가 신경망 가중치 학습 없이 라벨된 예시의 중심을 구성”한 것이며 “라벨 데이터가 전혀 필요 없는 방법”은 아니다. 두 임베딩 방법 차이는 48건 중 한 건이다. 정확도만으로 지연·RAM 우위를 실측했다고 표현하지 않는다.

### E. Rule의 confident가 실제 신뢰도를 뜻하지 않음 — 중요도 높음

코드에서 confident는 한 의도 키워드 집합만 매칭했다는 뜻이다. 보정된 확률이나 검증된 의미 신뢰도가 아니다. multi_match는 rules 배열의 첫 의도를 선택하므로 결제 키워드가 취소보다 앞선다.

기존 Rule 함수를 모델 호출 없이 실행한 진단 결과:

| 진단 입력 | 실제 반환 | 문제 |
|---|---|---|
| 결제하지 말고 처음으로 돌아갈래 | 결제, multi_match | 부정된 의도가 우선 선택됨 |
| 생일 카드 문구 알려줘 | 결제, confident | 키워드 OOD를 승인 |
| 취소하지 마세요 | 취소/처음으로, confident | 부정 처리 부재 |
| 주문하지 말고 도와주세요 | 옵션변경, multi_match | “말고” 키워드가 의미를 대신함 |

이는 이번 검토용 반례로 V1 점수에 합치지 않았다. no_match_only 정책은 위 발화를 LLM으로 넘기지 않는다. “오늘 날씨 알려줘”는 no_match로 LLM에 가지만 LLM prompt는 8개 중 하나를 강제하므로 명시적 OOD 계약이 없다.

조치: 기존 Rule을 회귀 baseline으로 보관하고, 새 Router에서는 좁은 전체 패턴과 부정·문맥·OOD 검증을 별도로 둔다. 고정 키워드 배열 순서를 의도 중요도의 검증 결과로 간주하지 않는다.

### F. Parser 교정 성과는 있으나 의미 검증은 여전히 부족 — 중요도 높음

최종 parser는 마지막 줄에 포함된 라벨/별칭 중 길이순 첫 항목을 택한다. 순수 함수 진단에서 `주문이 아니라 결제`를 주문으로 반환하며, `결제 또는 취소`를 결제로 반환한다. 생성이 비어 있고 마지막 줄이 prompt echo라면 `- 결제: 결제수단·영수증 ... (truncated)`도 결제로 처리할 수 있다.

이는 합성 raw 출력으로 검사한 parser의 동작이며, 최종 41/48에서 몇 건이 이 문제에 해당하는지는 전체 raw 출력이 없어 확인할 수 없다. 85.4%가 곧바로 거짓이라는 뜻은 아니다.

CLI 호출은 stdout만 반환하고 returncode를 검사하지 않으며 timeout 예외도 상태로 변환하지 않는다. 따라서 엔진 실패·무출력·형식 오류와 의미 미분류가 분리되지 않거나 평가 루프가 중단될 수 있다.

조치: 생성 영역과 로그를 구조적으로 구분하고, 원출력 전체를 보존한다. 정식 라벨/사전에 정한 별칭의 단일 일치만 승인한다. 복수 라벨·설명·무출력·timeout·비정상 종료는 별도 집계한다. 사후에 추가한 parser는 한 정밀도에만 적용하지 말고 저장 raw 전체를 동일 버전으로 재채점한다.

### G. 지연과 크기 지표의 의미를 바로잡아야 함 — 중요도 높음

Transformers의 측정은 모델 로딩 후 함수 호출 시간이며 tokenization, generation, decode가 포함된다. CLI의 전체 시간은 각 입력마다 프로세스와 모델을 다시 시작하는 경로다. Q4 최종 2052초/48건은 단순 평균 약 42.75초/건, f16은 3268초/48건으로 약 68.08초/건이지만, 출력·루프 overhead까지 들어간 전체시간 나눗셈이므로 warm 추론 latency로 보고하지 않는다.

Transformers 모델은 device_map=auto이며 실제 device map/GPU 모델·상태를 결과에 고정 기록하지 않았다. Phi만 eager attention을 명시했다. 모델 자체의 속도 차이와 backend·커널 차이를 분리할 수 없다. CUDA timing은 명시적 동기화 또는 이벤트로 보강할 수 있다. 다만 현재 함수가 decode 과정에서 CPU로 값을 옮기며 동기화했을 수 있으므로, synchronize 호출 부재만으로 모든 기존 시간이 틀렸다고 단정하지 않는다. [PyTorch 공식 timing 설명](https://docs.pytorch.org/docs/main/notes/cuda.html)

원본 크기 출력은 params×2/1024²의 추정치이고 단위는 MiB다. `ls -lh`의 4.9G/1.6G도 10진 GB와 구분해야 한다. 로그에는 원본 4986.92 MiB, Q4 텐서 1623.67 MiB 및 5.21 BPW가 기록되어 있으며 실제 Q4는 q4_K, q6_K, f32 등이 섞여 있다. 따라서 “모든 가중치가 정확히 4비트”, “1.6GB 파일이므로 RAM도 1.6GB”라고 표현하지 않는다. GGUF metadata 및 파일 overhead와 텐서 크기도 구분한다.

조치: Colab 내부에서도 CPU/GPU·runtime 트랙을 분리하고 cold load, warm intent latency, tokens, P50/P95, 메모리를 따로 기록한다. Rule 지연의 0ms 표기는 표시 정밀도/미측정과 구분한다. Android 수치는 추후 실기기에서 별도 측정한다.

### H. 재현성 및 추가 진단 사항 — 중요도 높음

메인 노트북의 Gemma 측정 셀은 NameError 출력이 남아 있고 함수 정의가 뒤에서 복구된다. 주석의 과거 성공 수치와 현재 저장 출력이 섞여 있다. 런타임 재시작, CPU 변경, git clone 최신 HEAD, 서로 다른 build의 결과가 누적되어 처음부터 순서대로 실행하는 단일 실험 기록이 아니다.

실제 모델 ID는 코드의 `google/gemma-2-2b-it`이며 저장 GGUF metadata도 gemma2/2B/it와 일치한다. 따라서 이전의 모호한 “Gemma 2B” 표기는 **Gemma 2 2B Instruct**로 구체화할 수 있다. 다만 원본 revision/hash는 별도 고정이 필요하다.

Transformers 호출은 apply_chat_template(tokenize=False) 후 tok(text)를 호출하며 add_special_tokens=False를 명시하지 않는다. 공식 문서는 이 경로에서 특수 토큰 중복 방지를 위해 해당 옵션을 지정하도록 안내한다. 실제 설치 버전/tokenizer에서 BOS가 중복됐는지 입력 token ID로 확인해야 하며, 이번 검토에서는 발생 사실이나 정확도 영향까지 확정하지 않는다. [Hugging Face 공식 설명](https://huggingface.co/docs/transformers/v4.44.2/chat_templating)

조치: 모델·tokenizer revision, runtime commit, 패키지 버전, 장치, prompt/parser hash, 데이터 hash, decoding 설정, 생성 raw와 예측을 하나의 run manifest로 묶는다. 독립 실험 셀은 전역 변수 상태에 의존하지 않도록 구성한다. 이는 다음 실험 단계의 제안이며 이번에 원본 코드를 바꾸지는 않았다.

## 5. 유지할 성과와 수정할 표현

| 기존 표현 | 권장 표현 |
|---|---|
| Hybrid 정확도 97.9%, LLM 4%로 실사용에 최적 | 기존 48행 개발셋에서 Rule과 저장된 Q4 예측을 조합한 재계산은 47/48, 호출 대상 2/48이었다. 새 발화 일반화는 미검증이다 |
| FP16/Q8/Q4 모두 무손실 85.4% | Q4의 template·parser 교정 후 41/48을 관측했다. Q8 최종값과 동일 조건 f16 비교는 추가 검증이 필요하다 |
| QAT 불필요 확정 | 현재 실제 양자화 손실을 분리하지 못했으므로 동일 조건 PTQ 비교 후 QAT 필요 여부를 결정한다 |
| QAT로 성능 회복 | 확인 가능한 회복은 template·parser 수정에 따른 관측값 변화다. QAT 수행 증거는 확인하지 못했다 |
| 247개 학습으로 임베딩 89.6% | 확인된 저장 실행은 학습 126개, 평가 48개에서 43/48이었다 |
| TinyLlama 작동 붕괴 | 해당 한국어 prompt·16토큰 제한·parser에서 48건 모두 정답 라벨을 얻지 못했다 |
| 정확도 상한 | 해당 개발셋과 시도한 설정에서 관측한 정확도 |
| 온디바이스 latency | Colab의 명시된 runtime/backend에서 측정한 시간. 모바일 추론 성능은 별도 측정 |

보존할 작업은 직접 GGUF 변환·PTQ 수행, 모델 ID·아키텍처 확인, template 누락과 echo/별칭 문제 발견, Rule·LLM의 서로 다른 오류 확인, 임베딩 비교 실험이다. 결과 전체를 폐기할 필요는 없다.

## 6. 새 설계 전 최소 재검증 순서

1. **즉시: 기록 정리.** V1 보고값과 이번 확인값을 별도 열에 보존한다. 247→126, Q8·f16 최종값 미확인, Gemma 원본 출력 미확인을 명시한다.
2. **최우선: 동일 조건 f16/Q8/Q4 재평가.** 처음에는 기존 48행을 회귀셋으로 사용한다. 공통 prompt/parser, 충분하고 동일한 출력 예산, raw·오류·시간을 저장한다. 이 단계는 새 일반화 평가가 아니다.
3. **최우선: 독립 test 설계.** 실제 도메인과 의도 경계를 확정하고 OOD·부정·복합·문맥 사례를 추가한다. 정답 예시와 유사 표현 묶음을 train/dev/test에 분산시키지 않는다.
4. **핵심: 모델·Rule·Hybrid 재비교.** 동결한 dev 설정으로 독립 test에 적용한다. Macro F1, 의도별 recall, OOD false acceptance, 재질문율과 호출률을 함께 본다.
5. **후속: 최적화.** 기존 측정 오류가 분리된 후 최신 모델, PTQ, token 최적화를 비교한다. 실제 손실·호환성이 확인될 때만 QAT를 진행한다.
6. **별도: 모바일 실측.** Colab 후보 선별과 Android 배포 성능을 구분한다. 앱의 STT·LLM·TTS 메모리 생명주기 및 발열을 측정한다.

## 7. 검토의 한계

이번 판단은 현재 Drive에 저장된 코드·출력·CSV와 앞서 제공된 보고서 기준이다. 없는 실행 기록을 과거에 실행하지 않았다는 증거로 취급하지 않는다. 모델 가중치를 다시 실행하지 않았고, 저장된 출력의 실제 실행 당시 코드·데이터 hash까지 검증할 수는 없다. 따라서 독립적으로 확인한 Rule·데이터 검산, 저장 출력 확인, 저장 예측 재구성을 구분해 보고했다.
