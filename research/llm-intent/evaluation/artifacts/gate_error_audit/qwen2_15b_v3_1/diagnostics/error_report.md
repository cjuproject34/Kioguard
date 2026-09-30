# Qwen/Qwen2-1.5B-Instruct gate error audit

이 문서는 계약 무효 출력의 내부 의미 오류를 확인하기 위한 진단이다. 기존 strict 점수를 대체하지 않는다.

- 사례: 20
- strict JSON: 20/20
- 정규화 JSON: 20/20
- 계약을 무시한 의도 순서 일치: 6/20
- 위험한 추가 행동: 2건
- must-not 위반: 2건

## 오류 범주

| 범주 | 사례 수 |
|---|---:|
| CONDITION | 7 |
| DANGEROUS_EXTRA | 2 |
| DEPENDENCY | 7 |
| FALLBACK | 4 |
| INTENT | 14 |
| MUST_NOT | 2 |
| REQUEST_COUNT | 7 |
| SLOTS | 20 |
| TARGET | 16 |

## 추가 request 키

| 키 | 사례 수 |
|---|---:|

세부 사례는 `case_error_audit.csv`에서 확인한다.
