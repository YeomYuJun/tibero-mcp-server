# Tibero MCP Server

Tibero 데이터베이스와 AI 어플리케이션 간의 안전한 통신을 제공하는 Model Context Protocol(MCP) 서버입니다.

## 참고 사항
기존 타 DB의 MCP를 참고하여 재구성한 MCP입니다.
실제 사용 시 SELECT 이외에는 유의해야합니다.

## 주요 기능

- **리소스 제공**: 데이터베이스 테이블과 뷰를 MCP 리소스로 노출
- **SQL 실행**: SELECT, INSERT, UPDATE, DELETE, DDL 쿼리 실행
- **스키마 정보**: 테이블 구조, 제약조건, 인덱스 정보 조회
- **샘플 데이터**: 테이블당 최대 100행의 샘플 데이터 제공

## 필요 환경

- Python 3.11+
- Java Runtime Environment 8+
- Tibero JDBC 드라이버 (tibero6-jdbc.jar) (*drivers 내부에 탑재 필요)

## 설치

```bash
pip install -r requirements.txt
```

## Claude Desktop 설정

`claude_desktop_config.json` 파일에 추가:

```json
{
  "mcpServers": {
    "tibero": {
      "command": "python",
      "args": ["/path/to/tibero_mcp_server/src/tibero_mcp_server/server.py"],
      "env": {
        "TIBERO_HOST": "localhost",
        "TIBERO_PORT": "8629",
        "TIBERO_SID": "tibero",
        "TIBERO_USER": "username",
        "TIBERO_PASSWORD": "password",
        "CLASSPATH": "/path/to/tibero6-jdbc.jar"
      }
    }
  }
}
```

## 제공 기능

### 1. 리소스 (Resources)
- **테이블**: `tibero://TABLE_NAME/data` - 테이블 스키마 + 샘플 데이터 (최대 100행)
- **뷰**: `tibero://VIEW_NAME/view` - 뷰 스키마 + 샘플 데이터

### 2. 도구 (Tools)

#### execute_sql
SQL 쿼리를 실행합니다.
- **SELECT/SHOW/DESC**: CSV 형태 결과 반환
- **INSERT/UPDATE/DELETE**: 영향받은 행 수 반환, 명시적 커밋
- **DDL**: 실행 결과 반환

#### get_table_info
테이블 상세 정보를 조회합니다.
- 컬럼 정보 (이름, 타입, 길이, NULL 허용)
- 제약조건 (PRIMARY KEY, UNIQUE, FOREIGN KEY, CHECK)
- 인덱스 정보 (이름, 유니크 여부)

## 실행

```bash
# 직접 실행
python src/tibero_mcp_server/server.py

# 모듈로 실행
python -m tibero_mcp_server.server
```

## 데이터베이스 연결

jaydebeapi를 사용하여 Tibero JDBC 드라이버로 연결합니다. DML 쿼리 실행 후 명시적으로 commit하며, 안전을 위해 AutoCommit=False로 설정됩니다.