# TinyLlama/TinyLlama-1.1B-Chat-v1.0 gate error audit

이 문서는 계약 무효 출력의 내부 의미 오류를 확인하기 위한 진단이다. 기존 strict 점수를 대체하지 않는다.

- 사례: 20
- strict JSON: 0/20
- 정규화 JSON: 0/20
- 계약을 무시한 의도 순서 일치: 3/20
- 위험한 추가 행동: 0건
- must-not 위반: 0건

## 오류 범주

| 범주 | 사례 수 |
|---|---:|
| CONDITION | 17 |
| DEPENDENCY | 17 |
| FALLBACK | 20 |
| INTENT | 17 |
| JSON_PARSE | 20 |
| REQUEST_COUNT | 17 |
| SLOTS | 17 |
| TARGET | 17 |

## 추가 request 키

| 키 | 사례 수 |
|---|---:|

세부 사례는 `case_error_audit.csv`에서 확인한다.
